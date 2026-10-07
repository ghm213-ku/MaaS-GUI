import sys

# Fix histogram_worker.py
worker_file = 'hardware/histogram_worker.py'
with open(worker_file, 'r') as f:
    content = f.read()

content = content.replace(
    'def __init__(self, start_channel, click_channel, user_name, binwidth, n_values, mode, auth_token=""):',
    'def __init__(self, start_channel, click_channel, user_name, binwidth, n_values, mode, auth_token="", is_mock=False):'
)

with open(worker_file, 'w') as f:
    f.write(content)

# Fix main_window.py
main_file = 'ui/main_window.py'
with open(main_file, 'r') as f:
    main_content = f.read()

target = """        self.hist_worker = HistogramWorker(
            start_channel=start_ch,
            click_channel=click_ch,
            user_name=user_name,
            binwidth=binwidth,
            n_values=n_values,
            mode=mode
        )"""

replacement = """        self.hist_worker = HistogramWorker(
            start_channel=start_ch,
            click_channel=click_ch,
            user_name=user_name,
            binwidth=binwidth,
            n_values=n_values,
            mode=mode,
            is_mock=self.force_mock
        )"""

main_content = main_content.replace(target, replacement)

with open(main_file, 'w') as f:
    f.write(main_content)
