from pathlib import Path
import numpy as np

def load_st_dataset(dataset):
    """
    Load spatio-temporal dataset based on dataset name.
    Output shape: [B, N, D]
    """
    base_dir = Path(__file__).resolve().parent.parent  # lib/ klasöründen çık
    data_paths = {
        'PEMS04': base_dir / 'data' / 'PEMS04' / 'PEMS04.npz',
        'PEMS08': base_dir / 'data' / 'PEMS08' / 'PEMS08.npz',
        'PEMS03': base_dir / 'data' / 'PEMS03' / 'PEMS03.npz',
        'PEMS07': base_dir / 'data' / 'PEMS07' / 'PEMS07.npz',
        'Kcetas': base_dir / 'data' / 'Kcetas' / 'morning_only.npz',
        'Konya': base_dir / 'data' / 'Konya' / 'konya_kavşak.npz',
        'Kayseri': base_dir / 'data' / 'Kayseri' / 'kayseri_kavsaklar.npz',
        'Kayseri_Serit': base_dir / 'data' / 'Kayseri' / 'kol_bazli_0.npz'
    }

    if dataset not in data_paths:
        raise ValueError(f"Dataset {dataset} not supported.")

    data_path = data_paths[dataset]
    if not data_path.exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    data = np.load(data_path)['data'][:, :, :1]
    print(f"✅ Loaded {dataset} with shape: {data.shape}")
    return data
