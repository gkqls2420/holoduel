from copy import deepcopy

def ids_from_cards(cards):
    return [card["game_card_id"] for card in cards]

def replace_field_in_conditions(effect, field_id, replacement_value):
    if "conditions" in effect:
        conditions = effect["conditions"]
        for condition in conditions:
            if field_id in condition:
                condition[field_id] = replacement_value

def is_card_resting(card):
    return "resting" in card and card["resting"]

def add_ids_to_effects(effects, player_id, card_id):
    for effect in effects:
        effect["player_id"] = player_id
        if card_id:
            effect["source_card_id"] = card_id

def get_owner_id_from_card_id(card_id):
    return card_id.split("_")[0]

def attach_card(attaching_card, target_card):
    card_type = attaching_card["card_type"]
    if card_type == "cheer":
        target_card["attached_cheer"].append(attaching_card)
    else:
        target_card["attached_support"].append(attaching_card)

def is_card_limited(card):
    return "limited" in card and card["limited"]

def is_event_card_whit_magic_tag_limited(card):
    return "magic_limited" in card and card["magic_limited"]

def is_card_attach_requirements_meant(attachment, card):
    if "effects" in attachment:
        first_effect = attachment["effects"][0]
        if first_effect["effect_type"] == "attach_card_to_holomem":
            to_limitation = first_effect.get("to_limitation", "")
            if to_limitation == "specific_member_name":
                name = first_effect.get("to_limitation_name", "")
                if name not in card["card_names"]:
                    return False
    return True

def is_card_sub_type(card, sub_type: str) -> bool:
    return "sub_type" in card and card["sub_type"] == sub_type

def get_cards_of_sub_type_from_holomems(sub_type: str, holomems: list) -> list:
    return [card for holomem in holomems for card in holomem["attached_support"] if is_card_sub_type(card, sub_type)]

def is_card_equipment(card):
    return any(is_card_sub_type(card, sub_type) for sub_type in ["mascot", "tool", "fan"])

def is_card_cheer(card):
    return card["card_type"] == "cheer"

def is_card_holomem(card):
    return card["card_type"] in ["holomem_debut", "holomem_bloom", "holomem_spot"]

def filter_effects_at_timing(effects, timing):
    return deepcopy([effect for effect in effects if effect.get("timing") == timing])
