from pathlib import Path

path = Path("routes/chat_routes.py")
text = path.read_text(encoding="utf-8")
old = "_actual_model or _answered_by or _requested_model"
new = "_actual_model or _answered_by or sess.model"
count = text.count(old)
if count != 4:
    raise RuntimeError(f"routes/chat_routes.py: expected 4 actual-model fallbacks, found {count}")
path.write_text(text.replace(old, new), encoding="utf-8")
print("Preserved resolved MOBS Auto model in metrics and persisted metadata")
