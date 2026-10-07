import re

file_path = "ui/main_window.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

target = """    def update_hist_filter_inputs_from_region(self):
        minX, maxX = self.hist_region.getRegion()
        self.hist_filter_min_input.setText(f"{minX:.2f}")
        self.hist_filter_max_input.setText(f"{maxX:.2f}")

    def update_hist_region_from_inputs(self):
        try:
            minX = float(self.hist_filter_min_input.text())
            maxX = float(self.hist_filter_max_input.text())
            self.hist_region.setRegion([minX, maxX])
        except ValueError:
            pass"""

replacement = """    def format_time_string(self, ps_val):
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
        return val

    def update_hist_filter_inputs_from_region(self):
        minX, maxX = self.hist_region.getRegion()
        self.hist_filter_min_input.setText(self.format_time_string(minX))
        self.hist_filter_max_input.setText(self.format_time_string(maxX))

    def update_hist_region_from_inputs(self):
        try:
            minX = self.parse_time_string(self.hist_filter_min_input.text())
            maxX = self.parse_time_string(self.hist_filter_max_input.text())
            self.hist_region.setRegion([minX, maxX])
        except ValueError:
            pass"""

content = content.replace(target, replacement)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
