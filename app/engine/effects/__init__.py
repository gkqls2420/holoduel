from app.engine.effects.power_boost import POWER_BOOST_HANDLERS
from app.engine.effects.card_movement import CARD_MOVEMENT_HANDLERS
from app.engine.effects.choose_decision import CHOOSE_DECISION_HANDLERS
from app.engine.effects.damage import DAMAGE_HANDLERS
from app.engine.effects.bloom_holomem import BLOOM_HOLOMEM_HANDLERS
from app.engine.effects.turn_record import TURN_RECORD_HANDLERS

EFFECT_HANDLERS = {}
EFFECT_HANDLERS.update(POWER_BOOST_HANDLERS)
EFFECT_HANDLERS.update(CARD_MOVEMENT_HANDLERS)
EFFECT_HANDLERS.update(CHOOSE_DECISION_HANDLERS)
EFFECT_HANDLERS.update(DAMAGE_HANDLERS)
EFFECT_HANDLERS.update(BLOOM_HOLOMEM_HANDLERS)
EFFECT_HANDLERS.update(TURN_RECORD_HANDLERS)
