import random
from copy import deepcopy
from app.gameengine import GameEngine
from app.card_database import CardDatabase
from app.engine.constants import EventType, GamePhase
from app.engine.models import GameAction


SORA_STARTER_DECK = {
    "hSD01-003": 4,
    "hSD01-004": 3,
    "hSD01-005": 3,
    "hSD01-006": 2,
    "hSD01-007": 2,
    "hSD01-008": 4,
    "hSD01-009": 3,
    "hSD01-010": 3,
    "hSD01-011": 2,
    "hSD01-012": 2,
    "hSD01-013": 2,
    "hSD01-014": 2,
    "hSD01-015": 2,
    "hSD01-016": 3,
    "hSD01-017": 3,
    "hSD01-018": 3,
    "hSD01-019": 3,
    "hSD01-020": 2,
    "hSD01-021": 2,
}
DEFAULT_CHEER = {"hY01-001": 10, "hY02-001": 10}
DEFAULT_OSHI = "hSD01-001"


def generate_deck_with(oshi_id, cards, cheer=None):
    """Generate a deck based on the Sora starter, replacing cards as needed."""
    deck = dict(SORA_STARTER_DECK)

    for card_id, count in cards.items():
        if card_id not in deck:
            total = sum(deck.values())
            if total + count > 50:
                for k in list(deck.keys()):
                    if deck[k] > 0 and total + count > 50:
                        reduce = min(deck[k], total + count - 50)
                        deck[k] -= reduce
                        total -= reduce
                        if deck[k] == 0:
                            del deck[k]
            deck[card_id] = count
        else:
            deck[card_id] = count

    total = sum(deck.values())
    while total < 50:
        deck["hSD01-003"] = deck.get("hSD01-003", 0) + 1
        total += 1
    while total > 50:
        for k in list(deck.keys()):
            if k.startswith("hSD01") and deck[k] > 1 and total > 50:
                deck[k] -= 1
                total -= 1

    return {
        "oshi_id": oshi_id or DEFAULT_OSHI,
        "deck": deck,
        "cheer_deck": cheer or DEFAULT_CHEER,
    }


class SeededRandom:
    """Deterministic random for tests."""
    def __init__(self, seed=42):
        self.rng = random.Random(seed)

    def random(self):
        return self.rng.random()

    def randint(self, a, b):
        return self.rng.randint(a, b)

    def shuffle(self, lst):
        self.rng.shuffle(lst)

    def choice(self, lst):
        return self.rng.choice(lst)

    def sample(self, population, k):
        return self.rng.sample(population, k)


def _find_event(events, event_type, player_id=None):
    """Find the last event matching the type (and optional player_id)."""
    for e in reversed(events):
        if e.get("event_type") == event_type:
            if player_id is None or e.get("event_player_id") == player_id:
                return e
    return None


def _find_all_events(events, event_type):
    return [e for e in events if e.get("event_type") == event_type]


def initialize_game_to_third_turn(test_case, p1_deck_info, p2_deck_info=None):
    """Initialize a game and advance to turn 3, P1's main step."""
    card_db = CardDatabase()
    if p2_deck_info is None:
        p2_deck_info = generate_deck_with(None, {})

    player_infos = [
        {
            "player_id": "p1",
            "username": "Player1",
            "oshi_id": p1_deck_info["oshi_id"],
            "deck": p1_deck_info["deck"],
            "cheer_deck": p1_deck_info["cheer_deck"],
        },
        {
            "player_id": "p2",
            "username": "Player2",
            "oshi_id": p2_deck_info["oshi_id"],
            "deck": p2_deck_info["deck"],
            "cheer_deck": p2_deck_info["cheer_deck"],
        },
    ]
    engine = GameEngine(card_db, "versus", player_infos)
    engine.set_random_test_hook(SeededRandom(42))
    engine.begin_game()
    events = engine.grab_events()

    # 1. First turn choice (starting player chooses to go first)
    engine.handle_game_message(engine.starting_player_id, GameAction.EffectResolution_MakeChoice, {"choice_index": 0})
    events = engine.grab_events()

    # 2-3. Handle mulligan, initial placement, backstage in a loop
    for _ in range(20):
        mulligan_ev = _find_event(events, "mulligan_decision")
        if mulligan_ev:
            active = mulligan_ev.get("active_player", engine.active_player_id)
            engine.handle_game_message(active, GameAction.Mulligan, {"do_mulligan": False})
            events = engine.grab_events()
            continue

        placement_ev = _find_event(events, "initial_placement_begin")
        if placement_ev:
            active = placement_ev.get("active_player", engine.active_player_id)
            player = engine.get_player(active)
            debut_options = [c["game_card_id"] for c in player.hand if c.get("card_type") == "holomem_debut"]
            if debut_options:
                engine.handle_game_message(active, GameAction.InitialPlacement, {
                    "center_holomem_card_id": debut_options[0],
                })
                events = engine.grab_events()
                continue

        return_ev = _find_event(events, "return_cards_begin")
        if return_ev:
            active = return_ev.get("active_player", engine.active_player_id)
            player = engine.get_player(active)
            return_count = return_ev.get("return_count", 0)
            hand_ids = [c["game_card_id"] for c in player.hand][:return_count]
            engine.handle_game_message(active, GameAction.ReturnCards, {"card_ids": hand_ids})
            events = engine.grab_events()
            continue

        backstage_ev = _find_event(events, "backstage_placement_begin")
        if backstage_ev:
            active = backstage_ev.get("active_player", engine.active_player_id)
            player = engine.get_player(active)
            debut_opts = [c["game_card_id"] for c in player.hand if c.get("card_type") == "holomem_debut"]
            spot_opts = [c["game_card_id"] for c in player.hand if c.get("card_type") == "holomem_spot"]
            place_ids = (debut_opts + spot_opts)[:5]
            engine.handle_game_message(active, GameAction.BackstagePlacement, {
                "backstage_holomem_card_ids": place_ids,
            })
            events = engine.grab_events()
            continue

        break

    # 4. Advance turns until turn >= 3 and P1 is active in main step
    def _handle_events(evts):
        """Process events and return new events, or None if nothing handled."""
        active = engine.active_player_id
        player = engine.get_player(active)

        # Check for cheer step (active player's version has real card IDs)
        for e in evts:
            if e.get("event_type") == "cheer_step" and e.get("event_player_id") == active:
                cheer_to_place = e.get("cheer_to_place", [])
                if cheer_to_place and cheer_to_place[0]:
                    target = player.center[0]["game_card_id"] if player.center else (
                        player.backstage[0]["game_card_id"] if player.backstage else None)
                    if target:
                        placements = {cid: target for cid in cheer_to_place}
                        engine.handle_game_message(active, GameAction.PlaceCheer, {"placements": placements})
                        return engine.grab_events()

        if _find_event(evts, "main_step_start"):
            engine.handle_game_message(active, GameAction.MainStepEndTurn, {})
            return engine.grab_events()

        if _find_event(evts, "performance_step_start"):
            engine.handle_game_message(active, GameAction.PerformanceStepEndTurn, {})
            return engine.grab_events()

        return None

    for _ in range(300):
        if engine.turn_number >= 3 and engine.active_player_id == "p1":
            if _find_event(events, "main_step_start"):
                break

        result = _handle_events(events)
        if result is not None:
            events = result
        else:
            break

    test_case.engine = engine
    test_case.player1 = "p1"
    test_case.player2 = "p2"
    return engine


def put_card_in_play(test_case, player, card_id, location):
    """Move a card from deck to the specified location (center, backstage, etc.)."""
    card = None
    for i, c in enumerate(player.deck):
        if c["card_id"] == card_id:
            card = player.deck.pop(i)
            break
    if card is None:
        for i, c in enumerate(player.hand):
            if c["card_id"] == card_id:
                card = player.hand.pop(i)
                break
    if card is None:
        raise ValueError(f"Card {card_id} not found in deck or hand for player {player.player_id}")
    card["played_this_turn"] = False
    card["bloomed_this_turn"] = False
    location.append(card)
    return card


def add_card_to_hand(test_case, player, card_id):
    """Move a card from deck to hand."""
    for i, c in enumerate(player.deck):
        if c["card_id"] == card_id:
            card = player.deck.pop(i)
            player.hand.append(card)
            return card
    raise ValueError(f"Card {card_id} not found in deck for player {player.player_id}")


def add_card_to_archive(test_case, player, card_id):
    """Move a card from deck to archive."""
    for i, c in enumerate(player.deck):
        if c["card_id"] == card_id:
            card = player.deck.pop(i)
            player.archive.append(card)
            return card
    raise ValueError(f"Card {card_id} not found in deck for player {player.player_id}")


def spawn_cheer_on_card(test_case, player, target_game_card_id, color, cheer_id_suffix):
    """Create a cheer card and attach it to a target holomem."""
    color_to_cheer = {
        "white": "hY01-001",
        "green": "hY02-001",
        "red": "hY03-001",
        "blue": "hY04-001",
        "purple": "hY05-001",
        "yellow": "hY06-001",
    }
    cheer_card_id = color_to_cheer.get(color, "hY01-001")
    card_db = test_case.engine.card_db
    cheer_def = card_db.get_card_by_id(cheer_card_id)
    cheer_card = deepcopy(cheer_def)
    cheer_card["owner_id"] = player.player_id
    cheer_card["game_card_id"] = f"{player.player_id}_cheer_{cheer_id_suffix}"

    target = None
    for card in player.center + player.backstage + player.collab:
        if card["game_card_id"] == target_game_card_id:
            target = card
            break
    if target is None:
        raise ValueError(f"Target card {target_game_card_id} not found on stage")
    target["attached_cheer"].append(cheer_card)
    test_case.engine.all_game_cards_map[cheer_card["game_card_id"]] = cheer_card["card_id"]
    return cheer_card


def begin_performance(test_case):
    """Start performance step."""
    engine = test_case.engine
    engine.handle_game_message(test_case.player1, GameAction.MainStepBeginPerformance, {})
    events = engine.grab_events()
    return events


def reset_mainstep(test_case):
    """Re-send main step actions and return the available actions list.
    Clears the existing decision first, then recalculates available actions."""
    engine = test_case.engine
    engine.clear_decision()
    engine.send_main_step_actions()
    events = engine.grab_events()
    for e in reversed(events):
        if e.get("event_type") == "decision_main_step" and e.get("event_player_id") == engine.active_player_id:
            return e.get("available_actions", [])
    return []


def use_oshi_action(test_case, skill_id):
    """Use an oshi skill."""
    engine = test_case.engine
    engine.handle_game_message(test_case.player1, GameAction.MainStepOshiSkill, {"skill_id": skill_id})
    return engine.grab_events()


def do_collab_get_events(test_case, player, card_id):
    """Execute a collab and return events."""
    engine = test_case.engine
    engine.handle_game_message(player.player_id, GameAction.MainStepCollab, {"card_id": card_id})
    return engine.grab_events()


def do_bloom(test_case, player, card_id, target_id):
    """Execute bloom and return events."""
    engine = test_case.engine
    engine.handle_game_message(player.player_id, GameAction.MainStepBloom, {
        "card_id": card_id,
        "target_id": target_id,
    })
    return engine.grab_events()


def pick_choice(test_case, player_id, choice_index):
    """Pick a choice from a decision_choice event."""
    engine = test_case.engine
    engine.handle_game_message(player_id, GameAction.EffectResolution_MakeChoice, {
        "choice_index": choice_index,
    })
    return engine.grab_events()


def do_cheer_step_on_card(test_case, card):
    """Handle cheer step by placing cheer on the given card."""
    engine = test_case.engine
    events = engine.grab_events()
    active = engine.active_player_id
    for e in events:
        if e.get("event_type") == "cheer_step" and e.get("event_player_id") == active:
            cheer_to_place = e.get("cheer_to_place", [])
            if cheer_to_place and cheer_to_place[0]:
                placements = {cid: card["game_card_id"] for cid in cheer_to_place}
                engine.handle_game_message(active, GameAction.PlaceCheer, {"placements": placements})
                return engine.grab_events()
    return events


def end_turn(test_case):
    """End the current turn."""
    engine = test_case.engine
    engine.handle_game_message(engine.active_player_id, GameAction.MainStepEndTurn, {})
    return engine.grab_events()


def set_next_die_rolls(test_case, rolls):
    """Set the next die roll results."""
    p1 = test_case.engine.get_player(test_case.player1)
    p1.set_next_die_roll = rolls[0] if rolls else 0


def change_oshi(test_case, player, oshi_id):
    """Change a player's oshi card."""
    card_db = test_case.engine.card_db
    new_oshi = deepcopy(card_db.get_card_by_id(oshi_id))
    new_oshi["game_card_id"] = player.player_id + "_oshi"
    player.oshi_card = new_oshi
    player.oshi_id = oshi_id


def validate_event(test_case, event, event_type, player_id=None, expected_data=None):
    """Validate an event has the expected type and data."""
    test_case.assertEqual(event.get("event_type"), event_type,
        f"Expected event type {event_type}, got {event.get('event_type')}")
    if player_id:
        test_case.assertEqual(event.get("event_player_id"), player_id)
    if expected_data:
        for key, value in expected_data.items():
            test_case.assertEqual(event.get(key), value,
                f"Event field '{key}': expected {value}, got {event.get(key)}")


def validate_last_event_not_error(test_case, events):
    """Validate that the last event is not an error."""
    test_case.assertTrue(len(events) > 0, "No events received")
    last_event = events[-1]
    test_case.assertNotEqual(last_event.get("event_type"), EventType.EventType_GameError,
        f"Last event is an error: {last_event.get('error', 'unknown')}")


def validate_last_event_is_error(test_case, events):
    """Validate that the last event IS an error."""
    test_case.assertTrue(len(events) > 0, "No events received")
    last_event = events[-1]
    test_case.assertEqual(last_event.get("event_type"), EventType.EventType_GameError)
