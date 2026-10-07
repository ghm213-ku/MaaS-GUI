import sys
import re

# 1. Update main.py
with open('main.py', 'r') as f:
    main_content = f.read()

main_content = main_content.replace(
    "window = MainWindow()",
    'force_mock = "testing" in sys.argv\n    window = MainWindow(force_mock=force_mock)'
)

with open('main.py', 'w') as f:
    f.write(main_content)

# 2. Update ui/main_window.py
with open('ui/main_window.py', 'r') as f:
    ui_content = f.read()

ui_content = ui_content.replace(
    "def __init__(self):",
    "def __init__(self, force_mock=False):"
)
ui_content = ui_content.replace(
    "super().__init__()",
    "super().__init__()\n        self.force_mock = force_mock"
)

# Inject is_mock=self.force_mock to worker instantions safely using regex
ui_content = re.sub(
    r'(self\.worker = CountRateWorker\([^)]*auth_token=self\.auth_token)\s*\)',
    r'\1, is_mock=self.force_mock)',
    ui_content
)

ui_content = re.sub(
    r'(self\.hist_worker = HistogramWorker\([^)]*auth_token=self\.auth_token)\s*\)',
    r'\1, is_mock=self.force_mock)',
    ui_content
)

ui_content = re.sub(
    r'(self\.coinc_worker = CoincidencesWorker\([^)]*auth_token=self\.auth_token)\s*\)',
    r'\1, is_mock=self.force_mock)',
    ui_content
)

with open('ui/main_window.py', 'w') as f:
    f.write(ui_content)

# 3. Update the three workers
for worker_file, cls_name in [('hardware/worker.py', 'CountRateWorker'), ('hardware/histogram_worker.py', 'HistogramWorker'), ('hardware/coincidences_worker.py', 'CoincidencesWorker')]:
    with open(worker_file, 'r') as f:
        content = f.read()
    
    if cls_name == "CountRateWorker" or cls_name == "CoincidencesWorker":
        content = content.replace(
            'def __init__(self, channels, user_name="maas-gui-client", binwidth=int(1e9), n_values=1000, refresh_rate=25, mode="Free Running", auth_token=""):',
            'def __init__(self, channels, user_name="maas-gui-client", binwidth=int(1e9), n_values=1000, refresh_rate=25, mode="Free Running", auth_token="", is_mock=False):'
        )
    elif cls_name == "HistogramWorker":
        content = content.replace(
            'def __init__(self, channels, user_name="maas-gui-client", binwidth=int(1e9), n_values=1000, mode="Start-Stop", auth_token=""):',
            'def __init__(self, channels, user_name="maas-gui-client", binwidth=int(1e9), n_values=1000, mode="Start-Stop", auth_token="", is_mock=False):'
        )
        
    content = content.replace(
        'self.is_mock = False\n        \n        atexit.register(self.force_teardown)',
        'self.is_mock = is_mock\n        \n        atexit.register(self.force_teardown)'
    )
    
    content = content.replace(
        '        # Book channels with a slight retry',
        '        # Book channels with a slight retry\n        if self.is_mock:\n            return\n'
    )
    
    with open(worker_file, 'w') as f:
        f.write(content)
