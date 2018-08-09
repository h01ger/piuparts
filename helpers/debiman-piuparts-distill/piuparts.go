// debiman-piuparts-distill extracts slave alternative links from
// LOG-ALTERNATIVES lines found in piuparts logs.
//
// See https://github.com/Debian/debiman/issues/12 for more details.
package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"io"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
)

var (
	logsDir = flag.String("logs_dir",
		"",
		"Directory containing piuparts logfiles")

	output = flag.String("output",
		"",
		"Path to write the (gzip-compressed, json-encoded) distilled links file to")

	parallel = flag.Int("parallel",
		10,
		"Number of logfiles to read in parallel")
)

var (
	logAlternativesRe = regexp.MustCompile(`LOG-ALTERNATIVES: dpkg=([^:]+): piuparts=(?:[^:]+): (.*)`)
	slaveParamsRe     = regexp.MustCompile(`--(?:install|slave) ([^ ]+) (?:[^ ]+) ([^ ]+)`)
)

type link struct {
	Pkg  string `json:"binpackage"`
	From string `json:"from"`
	To   string `json:"to"`
}

// process reads the piuparts logfile at path. links are extracted from each
// LOG-ALTERNATIVES line and written to the links channel.
func process(path string, links chan<- link) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	// Increase the maximum token size to 5 MB to handle logs such as
	// apprecommender_0.7.5-2.log, which has a very long line of interactive
	// xapian progress output.
	scanner.Buffer(nil, 5*1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if !strings.HasPrefix(line, "LOG-ALTERNATIVES: ") {
			continue
		}
		matches := logAlternativesRe.FindStringSubmatch(line)
		if matches == nil {
			continue
		}
		for _, param := range slaveParamsRe.FindAllStringSubmatch(line, -1) {
			links <- link{
				Pkg:  matches[1],
				From: param[1],
				To:   param[2],
			}
		}
	}
	return scanner.Err()
}

// byPkg is a helper type for sorting the results slice by binary package. Once
// Go 1.8 becomes available on piuparts.debian.org, we can switch to sort.Slice.
type byPkg []link

func (p byPkg) Len() int           { return len(p) }
func (p byPkg) Swap(i, j int)      { p[i], p[j] = p[j], p[i] }
func (p byPkg) Less(i, j int) bool { return p[i].Pkg < p[j].Pkg }

func main() {
	flag.Parse()

	if *output == "" {
		log.Fatal("-output must be specified")
	}

	if *logsDir == "" {
		log.Fatal("-logs_dir must be specified")
	}

	// Spawn -parallel worker goroutines, waiting for work
	work := make(chan string)
	linksChan := make(chan link)
	var wg sync.WaitGroup
	for i := 0; i < *parallel; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for path := range work {
				if err := process(path, linksChan); err != nil {
					log.Printf("error processing %q: %v", path, err)
				}
			}
		}()
	}
	// Collect results from all workers into linksMap
	linksMap := make(map[link]bool)
	// Channel for signaling that all results were collected
	collected := make(chan bool)
	go func() {
		for l := range linksChan {
			linksMap[l] = true
		}
		collected <- true
	}()
	// Walk through *logsDir, enqueue all .log files onto the work channel
	if err := filepath.Walk(*logsDir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if strings.HasSuffix(path, ".log") && info != nil && info.Mode().IsRegular() {
			work <- path
		}
		return nil
	}); err != nil {
		log.Fatal(err)
	}
	// Close the channel, signaling termination to the worker goroutines
	close(work)
	// Wait for the worker goroutines to terminate
	wg.Wait()
	close(linksChan)
	<-collected
	// Convert the unsorted linksMap into a slice for sorting
	links := make([]link, 0, len(linksMap))
	for l := range linksMap {
		links = append(links, l)
	}
	// for easier debugging of the resulting file:
	sort.Stable(byPkg(links))

	if err := writeAtomically(*output, true, func(w io.Writer) error {
		return json.NewEncoder(w).Encode(&links)
	}); err != nil {
		log.Fatal(err)
	}
}
