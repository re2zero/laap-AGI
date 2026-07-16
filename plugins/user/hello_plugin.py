def metadata():
    return {"name": "hello_plugin", "version": "1.0.0", "capabilities": ["greeting", "self_awareness"]}

_call_count = 0

def on_load(bus, registry):
    bus.set_modulators(activation=0.65)
    bus.set_curiosity(0.7)

def before_turn(user_message, bus):
    global _call_count
    _call_count += 1
    if "hello" in user_message.lower() or "hi" in user_message.lower():
        bus.set_emotion(valence="positive_high", arousal=0.7, dominance=0.6)
