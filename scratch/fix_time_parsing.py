import re

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    def format_time_string(self, ps_val):
        abs_val = abs(ps_val)
        if abs_val >= 1e12:
            return f"{ps_val / 1e12:.3g}s"
        elif abs_val >= 1e9:
            return f"{ps_val / 1e9:.3g}ms"
        elif abs_val >= 1e6:
            return f"{ps_val / 1e6:.3g}us"
        elif abs_val >= 1e3:
            return f"{ps_val / 1e3:.3g}ns"
        else:
            return f"{ps_val:.3g}ps"

    def parse_time_string(self, text):
        import re
        text = text.strip().lower()
        match = re.match(r"^(-?[\d\.]+(?:e-?\d+)?)\s*(ps|ns|us|ms|s)?$", text)
        if not match:
            raise ValueError("Invalid format")
        val_str, unit = match.groups()
        val = float(val_str)
        if unit == "s":
            val *= 1e12
        elif unit == "ms":
            val *= 1e9
        elif unit == "us":
            val *= 1e6
        elif unit == "ns":
            val *= 1e3
        return val"""

replacement = """    def format_time_string(self, s_val):
        abs_val = abs(s_val)
        if abs_val == 0:
            return "0s"
        elif abs_val >= 1.0:
            return f"{s_val:.3g}s"
        elif abs_val >= 1e-3:
            return f"{s_val * 1e3:.3g}ms"
        elif abs_val >= 1e-6:
            return f"{s_val * 1e6:.3g}us"
        elif abs_val >= 1e-9:
            return f"{s_val * 1e9:.3g}ns"
        else:
            return f"{s_val * 1e12:.3g}ps"

    def parse_time_string(self, text):
        import re
        text = text.strip().lower()
        match = re.match(r"^(-?[\d\.]+(?:e-?\d+)?)\s*(ps|ns|us|ms|s)?$", text)
        if not match:
            raise ValueError("Invalid format")
        val_str, unit = match.groups()
        val = float(val_str)
        if unit == "ms":
            val *= 1e-3
        elif unit == "us":
            val *= 1e-6
        elif unit == "ns":
            val *= 1e-9
        elif unit == "ps":
            val *= 1e-12
        return val"""

content = content.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
