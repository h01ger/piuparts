import unittest

import piupartslib.conf as conf
import distro_info


class ConfStdDistroTests(unittest.TestCase):

    def setUp(self):
        self.cobj = conf.Config('notimportant', {})

        debdist = distro_info.DebianDistroInfo()
        self.stable = debdist.stable()
        self.unstable = debdist.devel()
        self.oldstable = debdist.old()
        self.testing = debdist.testing()
        self.experimental = 'experimental'

    def testConfStdDistroNames(self):
        self.assertEqual(self.oldstable, 'squeeze')
        self.assertEqual(self.stable, 'wheezy')
        self.assertEqual(self.testing, 'jessie')
        self.assertEqual(self.unstable, 'sid')
        self.assertEqual(self.experimental, 'experimental')

    def testConfMapDistro(self):

        self.assertEqual(self.cobj._map_distro('bogus'), 'unknown')

        self.assertEqual(self.cobj._map_distro(self.oldstable), 'oldstable')
        self.assertEqual(self.cobj._map_distro(self.stable), 'stable')
        self.assertEqual(self.cobj._map_distro(self.testing), 'testing')
        self.assertEqual(self.cobj._map_distro(self.unstable), 'unstable')
        self.assertEqual(self.cobj._map_distro(self.experimental), 'experimental')

        self.assertEqual(self.cobj._map_distro('oldstable'), 'oldstable')
        self.assertEqual(self.cobj._map_distro('stable'), 'stable')
        self.assertEqual(self.cobj._map_distro('testing'), 'testing')
        self.assertEqual(self.cobj._map_distro('unstable'), 'unstable')
        self.assertEqual(self.cobj._map_distro('experimental'), 'experimental')

    def testConfMapProposedDistro(self):

        self.assertEqual(
            self.cobj._map_distro('stable-proposed'), 'stable')
        self.assertEqual(
            self.cobj._map_distro(self.stable + '-proposed'), 'stable')

    def testConfMapRemainingDistros(self):

        self.assertEqual(self.cobj._map_distro('rc-buggy'), 'experimental')

        self.assertEqual(
            self.cobj._map_distro('Debian6.0.9'),
             self.cobj._map_distro('squeeze'))
        self.assertEqual(
            self.cobj._map_distro('Debian7.4'),
             self.cobj._map_distro('wheezy'))
        self.assertEqual(
            self.cobj._map_distro('Debian8'),
             self.cobj._map_distro('jessie'))
        self.assertEqual(
            self.cobj._map_distro('Debian8.1'),
             self.cobj._map_distro('jessie'))

    def testConfGetStdDistro(self):

        for std in [
                'oldstable', 'stable', 'testing', 'unstable', 'experimental']:
            self.assertEqual(
                self.cobj.get_std_distro([self.__dict__[std]]), std)
            self.assertEqual(
                self.cobj.get_std_distro([self.__dict__[std], 'unknown']), std)
            self.assertEqual(
                self.cobj.get_std_distro(['unknown', self.__dict__[std]]), std)
            self.assertEqual(
                self.cobj.get_std_distro(
                    ['unknown', 'unknown', self.__dict__[std]]), std)
            self.assertEqual(
                self.cobj.get_std_distro(
                    [self.__dict__[std], 'unknown', 'unknown']), std)

        self.assertEqual(self.cobj.get_std_distro(['unknown']), 'unknown')
        self.assertEqual(
            self.cobj.get_std_distro(['unknown', 'unknown']), 'unknown')
