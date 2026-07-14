import unittest

from mads_loremaster.lua_table import LuaParseError, parse_lua_table


class LuaTableParserTests(unittest.TestCase):
    def test_nested_quest_row_subset(self):
        value = parse_lua_table('{"Quest \\"Name\\"",{{123}},nil,-25,70,true,{[331]={{48.9,69.5}}}}')
        self.assertEqual(value[0], 'Quest "Name"')
        self.assertEqual(value[1], [[123]])
        self.assertIsNone(value[2])
        self.assertEqual(value[3], -25)
        self.assertEqual(value[4], 70)
        self.assertIs(value[5], True)
        self.assertEqual(value[6][331], [[48.9, 69.5]])

    def test_rejects_code(self):
        with self.assertRaises(LuaParseError):
            parse_lua_table("{os.execute('nope')}")


if __name__ == "__main__":
    unittest.main()
