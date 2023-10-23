from pathlib import Path
from urllib.request import urlretrieve

#---------------------------------------------

# (url, local file)
sources = [
    (
        "https://data.iledefrance.fr/api/explore/v2.1/catalog/datasets/base-comparateur-de-territoires/exports/geojson?lang=fr&timezone=Europe%2FBerlin",
        "base-comparateur-de-territoires.geojson",
    ),

    (
        "https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets/emplacement-des-gares-idf/exports/geojson?lang=fr&timezone=Europe%2FBerlin",
        "emplacement-des-gares-idf.geojson",
    ),

    (
        "https://data.iledefrance-mobilites.fr/api/explore/v2.1/catalog/datasets/traces-du-reseau-ferre-idf/exports/geojson?lang=fr&timezone=Europe%2FBerlin",
        "traces-du-reseau-ferre-idf.geojson",
    ),
]

#---------------------------------------------

def main():
    for url, local_file in sources:
        downloadDataset(url, local_file)

#---------------------------------------------

RAW_DATA_ROOT = Path(__file__).parent.parent.joinpath("data", "raw")

def downloadDataset(url, local_file):
    target_path = RAW_DATA_ROOT.joinpath(local_file)
    if not target_path.exists():
        print(f"Downloading '{url}' to '{target_path}'...")
        urlretrieve(url, target_path)

#---------------------------------------------

if __name__ == '__main__':
    main()

