import unittest
from app.card_database import CardDatabase


class Test_hBP02_053_CardDefinition(unittest.TestCase):
    """
    Test cases for hBP02-053 (Kureiji Ollie 2nd Bloom) card definition
    Verifies the card is properly defined in the database.
    """

    def setUp(self):
        self.card_db = CardDatabase()
        self.card = self.card_db.get_card_by_id("hBP02-053")

    def test_card_exists(self):
        """Test that hBP02-053 card exists in the database"""
        self.assertIsNotNone(self.card, "hBP02-053 card should exist in database")

    def test_card_basic_properties(self):
        """Test basic card properties"""
        self.assertEqual(self.card["card_id"], "hBP02-053")
        self.assertEqual(self.card["card_type"], "holomem_bloom")
        self.assertEqual(self.card["bloom_level"], 2)
        self.assertIn("kureiji_ollie", self.card["card_names"])

    def test_card_stats(self):
        """Test card stats"""
        self.assertEqual(self.card["hp"], 190)
        self.assertEqual(self.card["baton_cost"], 2)
        self.assertEqual(self.card["rarity"], "rr")
        self.assertIn("yellow", self.card["colors"])

    def test_card_tags(self):
        """Test card tags"""
        self.assertIn("#ID", self.card["tags"])
        self.assertIn("#IDGen2", self.card["tags"])
        self.assertIn("#language", self.card["tags"])

    def test_art_definition(self):
        """Test art 'calculatedtactics' is defined"""
        arts = self.card["arts"]
        self.assertEqual(len(arts), 1)
        
        art = arts[0]
        self.assertEqual(art["art_id"], "calculatedtactics")
        self.assertEqual(art["power"], 100)
        
        # Check costs: purple 1 + any 2
        costs = art["costs"]
        self.assertEqual(len(costs), 2)
        purple_cost = next((c for c in costs if c["color"] == "purple"), None)
        any_cost = next((c for c in costs if c["color"] == "any"), None)
        self.assertIsNotNone(purple_cost)
        self.assertIsNotNone(any_cost)
        self.assertEqual(purple_cost["amount"], 1)
        self.assertEqual(any_cost["amount"], 2)

    def test_art_effects(self):
        """Test art effects are defined"""
        art = self.card["arts"][0]
        art_effects = art.get("art_effects", [])
        self.assertEqual(len(art_effects), 2)
        
        # Effect 1: vs blue target +50
        blue_effect = art_effects[0]
        self.assertEqual(blue_effect["effect_type"], "power_boost")
        self.assertEqual(blue_effect["amount"], 50)
        self.assertIn("conditions", blue_effect)
        
        # Effect 2: IDGen2 2nd bloom condition +40
        idgen2_effect = art_effects[1]
        self.assertEqual(idgen2_effect["effect_type"], "power_boost")
        self.assertEqual(idgen2_effect["amount"], 40)

    def test_bloom_effects(self):
        """Test bloom effects are defined"""
        bloom_effects = self.card.get("bloom_effects", [])
        self.assertGreater(len(bloom_effects), 0)
        
        # Check for archive_from_hand choice effect
        choice_effect = bloom_effects[0]
        self.assertEqual(choice_effect["effect_type"], "choice")


if __name__ == '__main__':
    unittest.main()
