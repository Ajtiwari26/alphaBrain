import json

def parse_verdict_line(output: str, valid_enums: list[str], default_verdict: str) -> str:
    if not output:
        return default_verdict

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return default_verdict

    try:
        def reject_duplicates(ordered_pairs):
            d = {}
            for k, v in ordered_pairs:
                if k in d:
                    raise ValueError(f"Duplicate key: {k}")
                d[k] = v
            return d

        def is_valid_marker(line: str) -> str | None:
            try:
                parsed = json.loads(line, object_pairs_hook=reject_duplicates)
                if isinstance(parsed, dict) and len(parsed) == 1 and "verdict" in parsed:
                    val = parsed["verdict"]
                    if isinstance(val, str) and val in valid_enums:
                        return val
            except Exception:
                pass
            return None

        valid_markers = []
        for i, line in enumerate(lines):
            marker_val = is_valid_marker(line)
            if marker_val:
                valid_markers.append((i, marker_val))

        if len(valid_markers) != 1:
            return default_verdict

        marker_idx, marker_val = valid_markers[0]
        if marker_idx != len(lines) - 1:
            return default_verdict

        return marker_val

    except Exception:
        return default_verdict

print("1.", parse_verdict_line('{"verdict": "APPROVE"}', ["APPROVE"], "REJECT") == "APPROVE")
print("2.", parse_verdict_line('{"verdict": "APPROVE"}\n{"verdict": "APPROVE"}', ["APPROVE"], "REJECT") == "REJECT")
print("3.", parse_verdict_line('{"verdict": "APPROVE"}\nsome text', ["APPROVE"], "REJECT") == "REJECT")
print("4.", parse_verdict_line('some text\n{"verdict": "APPROVE"}', ["APPROVE"], "REJECT") == "APPROVE")
