import numpy as np
import time
import os

def generate_dummy_data():
    all_channels = []
    for hundreds in range(1, 7):
        for i in range(1, 19):
            all_channels.append(hundreds * 100 + i)
            
    dummy_data = {ch: np.random.randint(100, 1000) for ch in all_channels}
    np.save('dummy_data.npy', dummy_data)
    print("Generated dummy_data.npy")

if __name__ == '__main__':
    generate_dummy_data()
