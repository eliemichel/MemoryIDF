"""
This script is a bit messy, because it handles data that is a bit messy itself.
"""

from pathlib import Path
import json
from dataclasses import dataclass, field
from typing import List, Dict
from collections import defaultdict
from urllib.request import urlretrieve

#---------------------------------------------

def main():
    traces = loadData("traces-du-reseau-ferre-idf.geojson")
    stations = loadData("emplacement-des-gares-idf.geojson")
    communes = loadData("base-comparateur-de-territoires.geojson")
    memory_paris = loadData("../memory-pour-paris.geojson")

    reg = buildRegistry(traces, stations)
    #reg.prettyPrint()

    reg = downloadImages(reg)

    new_stations = generateNewStations(stations, reg)
    exportData(new_stations, "memory-pour-idf-stations.geojson")

    new_traces = generateNewTraces(traces, reg)
    exportData(new_traces, "memory-pour-idf-trainline-traces.geojson")

    new_communes = generateCommunes(communes)
    exportData(new_communes, "memory-pour-idf-communes.geojson")

    from_memory_paris = generateConversionFromMemoryParis(memory_paris, new_stations)

    metadata = generateMetadata(stations, reg, new_communes, from_memory_paris)
    exportData(metadata, "memory-pour-idf-metadata.json")

#---------------------------------------------

DATA_ROOT = Path(__file__).parent.parent.joinpath("data")

def loadData(filename):
    with open(DATA_ROOT.joinpath("raw", filename), encoding="utf-8") as f:
        return json.load(f)

def exportData(data, filename):
    with open(DATA_ROOT.joinpath(filename), "w", encoding="utf-8") as f:
        return json.dump(data, f)

#---------------------------------------------

@dataclass
class RegistryLineEntry:
    color: str
    logo: str
    logo_svg_url: str | None = None
    logo_filename: str | None = None

LineKey = str

@dataclass
class RegistryStationEntry:
    ids: List[str] = field(default_factory=list)
    trainline_key: LineKey | None = None

StationKey = str

@dataclass
class Registry:
    """Metadata extracted from datasets"""
    trainlines: Dict[LineKey, RegistryLineEntry] = field(default_factory=dict)

    connected_stations: Dict[StationKey, RegistryStationEntry] = field(default_factory=dict)

    def prettyPrint(self):
        print("== Train line metadata ==")
        for k, v in self.trainlines.items():
            print(f" - {Registry.formatKey(k)}: {v.logo}")

    @staticmethod
    def formatKey(key):
        mode, line = key
        mode = {
            "TRAMWAY": "T",
            "METRO": "M",
        }.get(mode, mode)
        return f"{mode} {line}"

    @staticmethod
    def makeKeyFromTraceProps(props):
        mode = props['mode']
        line = props['indice_lig']
        if mode == 'TRAMWAY':
            line = {
                "3bis": "3B",
                "3": "3A",
            }.get(line, line)
        if mode == 'TER' and line in {'C', 'D'}:
            mode = 'RER'
        if mode == 'RER' and line == 'TER':
            line = 'D'
        if line == "GL":
            mode = "TER"
            line = "TER"
        return (mode, line)

    @staticmethod
    def makeKeyFromStationProps(props):
        mode = props['mode']
        mode = {
            "VAL": "NAVETTE",
        }.get(mode, mode)
        line = props['indice_lig']
        line = {
            "7b": "7bis",
        }.get(line, line)
        if line == "GL":
            mode = "TER"
            line = "TER"
        return (mode, line)

    @staticmethod
    def mergeEntries(a, b):
        if b is None:
            return a
        return RegistryLineEntry(
            color = a.color if a.color is not None else b.color,
            logo = a.logo if a.logo is not None else b.logo,
        )

#---------------------------------------------

def buildRegistry(traces, stations):
    reg = Registry()

    # Traces
    for segment in traces['features']:
        props = segment['properties']

        entry = RegistryLineEntry(
            color = props['colourweb_hexa'],
            logo = props['picto_final'],
        )
        key = Registry.makeKeyFromTraceProps(props)
        reg.trainlines[key] = Registry.mergeEntries(entry, reg.trainlines.get(key))

    for k, entry in reg.trainlines.items():
        assert(entry.color is not None)
        if entry.logo is None:
            print(f"WARNING: No logo for line {Registry.formatKey(k)}")

    # Stations
    for station in stations['features']:
        props = station['properties']
        trainline_key = Registry.makeKeyFromStationProps(props)

        id = fixDuplicateGareId(props)
        name = props['nom_zdc']
        entry = reg.connected_stations.get(name, RegistryStationEntry())
        entry.ids.append(id)
        entry.trainline_key = trainline_key
        reg.connected_stations[name] = entry

        picto = props['picto']
        if picto is not None:
            name = picto['filename']
            url = f"https://data.iledefrance-mobilites.fr/explore/dataset/emplacement-des-gares-idf/files/{picto['id']}/download/"
            reg.trainlines[trainline_key].logo_svg_url = url
            reg.trainlines[trainline_key].logo_filename = name

    return reg

#---------------------------------------------

image_overrides = {
    'TER TER': "TER_TER.svg", # non fourni
    'NAVETTE ORL': "NAVETTE ORL.svg", # non fourni (à compléter, image vide pour le moment)
    'NAVETTE CDG': "NAVETTE CDG.svg", # non fourni (à compléter, image vide pour le moment)
    'NAVETTE FUN': "NAVETTE FUN.svg", # non fourni (à compléter, image vide pour le moment)
    'T 14': "T 14.svg", # fourni comme .png alors que la donnée est .svg (et j'ai manuellement retiré le fond blanc du svg)
}

def downloadImages(reg):
    for key, entry in reg.trainlines.items():
        override = image_overrides.get(Registry.formatKey(key))
        if override is not None:
            entry.logo_filename = override
            logo_url = None
        elif entry.logo_svg_url is not None:
            assert(entry.logo_filename is not None)
            logo_url = entry.logo_svg_url
        else:
            entry.logo_filename = Registry.formatKey(key) + ".png"
            logo_url = entry.logo
        if logo_url is not None:
            filename = DATA_ROOT.joinpath("images", entry.logo_filename)
            if not filename.exists():
                print(f"Downloading '{logo_url}' into '{filename}'...")
                urlretrieve(logo_url, filename)
    return reg

#---------------------------------------------

def generateMetadata(stations, reg, new_communes, from_memory_paris):
    station_count_per_line = defaultdict(int)
    for station in stations['features']:
        props = station['properties']
        trainline_key = Registry.makeKeyFromStationProps(props)
        station_count_per_line[Registry.formatKey(trainline_key)] += 1

    ordered_trainlines = [
        "M 1",
        "M 2",
        "M 3",
        "M 3bis",
        "M 4",
        "M 5",
        "M 6",
        "M 7",
        "M 7bis",
        "M 8",
        "M 9",
        "M 10",
        "M 11",
        "M 12",
        "M 13",
        "M 14",
        "RER A",
        "RER B",
        "RER C",
        "RER D",
        "RER E",
        "TRAIN H",
        "TRAIN J",
        "TRAIN K",
        "TRAIN L",
        "TRAIN N",
        "TRAIN P",
        "TRAIN R",
        "TRAIN U",
        "TRAIN V",
        "T 1",
        "T 2",
        "T 3A",
        "T 3B",
        "T 4",
        "T 5",
        "T 6",
        "T 7",
        "T 8",
        "T 9",
        "T 10",
        "T 11",
        "T 12",
        "T 13",
        "T 14",
        "NAVETTE CDG",
        "NAVETTE FUN",
        "NAVETTE ORL",
        #"TER GL",
        "TER TER",
        "CABLE 1",
    ]

    trainline_logo_style = {
        "M 1":         { "text-color": "black", "shape": "circle" },
        "M 2":         { "text-color": "white", "shape": "circle" },
        "M 3":         { "text-color": "white", "shape": "circle" },
        "M 3bis":      { "text-color": "black", "shape": "circle" },
        "M 4":         { "text-color": "white", "shape": "circle" },
        "M 5":         { "text-color": "black", "shape": "circle" },
        "M 6":         { "text-color": "black", "shape": "circle" },
        "M 7":         { "text-color": "black", "shape": "circle" },
        "M 7bis":      { "text-color": "black", "shape": "circle" },
        "M 8":         { "text-color": "black", "shape": "circle" },
        "M 9":         { "text-color": "black", "shape": "circle" },
        "M 10":        { "text-color": "black", "shape": "circle" },
        "M 11":        { "text-color": "white", "shape": "circle" },
        "M 12":        { "text-color": "white", "shape": "circle" },
        "M 13":        { "text-color": "white", "shape": "circle" },
        "M 14":        { "text-color": "white", "shape": "circle" },
        "RER A":       { "text-color": "white", "shape": "rounded-square" },
        "RER B":       { "text-color": "white", "shape": "rounded-square" },
        "RER C":       { "text-color": "black", "shape": "rounded-square" },
        "RER D":       { "text-color": "white", "shape": "rounded-square" },
        "RER E":       { "text-color": "white", "shape": "rounded-square" },
        "TRAIN H":     { "text-color": "white", "shape": "rounded-square" },
        "TRAIN J":     { "text-color": "black", "shape": "rounded-square" },
        "TRAIN K":     { "text-color": "white", "shape": "rounded-square" },
        "TRAIN L":     { "text-color": "black", "shape": "rounded-square" },
        "TRAIN N":     { "text-color": "white", "shape": "rounded-square" },
        "TRAIN P":     { "text-color": "black", "shape": "rounded-square" },
        "TRAIN R":     { "text-color": "black", "shape": "rounded-square" },
        "TRAIN U":     { "text-color": "white", "shape": "rounded-square" },
        "TRAIN V":     { "text-color": "white", "shape": "rounded-square" },
        "T 1":         { "text-color": "black", "shape": "square" },
        "T 2":         { "text-color": "black", "shape": "square" },
        "T 3A":        { "text-color": "black", "shape": "square" },
        "T 3B":        { "text-color": "black", "shape": "square" },
        "T 4":         { "text-color": "black", "shape": "square" },
        "T 5":         { "text-color": "black", "shape": "square" },
        "T 6":         { "text-color": "black", "shape": "square" },
        "T 7":         { "text-color": "black", "shape": "square" },
        "T 8":         { "text-color": "black", "shape": "square" },
        "T 9":         { "text-color": "black", "shape": "square" },
        "T 10":        { "text-color": "black", "shape": "square" },
        "T 11":        { "text-color": "black", "shape": "square" },
        "T 12":        { "text-color": "black", "shape": "square" },
        "T 13":        { "text-color": "black", "shape": "square" },
        "T 14":        { "text-color": "black", "shape": "square" },
        "NAVETTE CDG": { "text-color": "white", "shape": "square" },
        "NAVETTE FUN": { "text-color": "white", "shape": "square" },
        "NAVETTE ORL": { "text-color": "white", "shape": "square" },
        #"TER GL":      { "text-color": "white", "shape": "square" },
        "TER TER":     { "text-color": "white", "shape": "rounded-square" },
        "CABLE 1":     { "text-color": "black", "shape": "square" },
    }

    total_inhabitants = 0
    total_surface = 0
    for feature in new_communes["features"]:
        props = feature["properties"]
        total_inhabitants += props["population"]
        total_surface += props["superficie"]
    print(f"Nombre total d'habitants: {total_inhabitants}")
    print(f"Supercifie total (en km2): {total_surface}")

    assert(set(ordered_trainlines) == set(trainline_logo_style.keys()))

    return {
        "connected-stations": {
            id: connected.ids
            for connected in reg.connected_stations.values()
            if len(connected.ids) > 1
            for id in connected.ids
        },
        "trainlines": {
            Registry.formatKey(key): {
                "station-count": station_count_per_line[Registry.formatKey(key)],
                "logo": entry.logo_filename,
                "logo-style": trainline_logo_style[Registry.formatKey(key)],
            }
            for key, entry in reg.trainlines.items()
        },
        "ordered-trainlines": ordered_trainlines,
        "communes": {
            "total-communes": len(new_communes["features"]),
            "total-inhabitants": total_inhabitants,
            "total-surface": total_surface,
        },
        "from-memory-paris": from_memory_paris,
    }

#---------------------------------------------

def filterGeojsonProperties(geojson, filterProperties):
    return {
        "type": geojson["type"],
        "features": [
            {
                "type": entry["type"],
                "geometry": entry["geometry"],
                "properties": new_props,
            }
            for entry in geojson["features"]
            for new_props in filterProperties(entry["properties"].copy())
        ],
    }

#---------------------------------------------

def fixDuplicateGareId(props):
    # There are 3 cases of id collision
    if (
        #(props["nom_gares"] == "Saint-Cyr" and props["tertram"] == "TRAM 13")
        #or (props["nom_gares"] == "Montreuil - Hôpital" and props["res_com"] == "METRO 11")
        #or (props["nom_gares"] == "Esbly" and props["tertrain"] == "TRAIN P")
        (props["nom_gares"] == "Mairie d'Aubervilliers" and props["res_com"] == "METRO 12")
        or (props["nom_gares"] == "Villejuif - Gustave Roussy" and props["res_com"] == "METRO 14")
        or (props["nom_gares"] == "Esbly" and props["res_com"] == "TRAM 14")
    ):
        return props['id_gares'] + 9000000
    else:
        return props['id_gares']

#---------------------------------------------

def generateNewStations(stations, reg):
    def filterEntry(props):
        return props["mode"] != 'TER'
    
    def filterProperties(props):
        key = Registry.makeKeyFromStationProps(props)
        #if props["mode"] == 'TER' or key[0] in {'TER', 'NAVETTE'}:
        if key[0] == 'NAVETTE':
            return []
        if key[0] == 'TRAM':
            key = ('TRAMWAY', key[1])

        meta = reg.trainlines.get(key)
        assert(meta is not None)
        assert(Registry.formatKey(key) != "TER GL")
        props['color'] = '#' + meta.color
        props['logo'] = "data/images/" + meta.logo_filename
        props['trainline'] = Registry.formatKey(key)

        props['id_gares'] = fixDuplicateGareId(props)
        return [props]

    return filterGeojsonProperties(stations, filterProperties)

#---------------------------------------------

def generateNewTraces(traces, reg):
    def filterProperties(props):
        key = Registry.makeKeyFromTraceProps(props)
        #if props["mode"] == 'TER' or key[0] == 'NAVETTE':
        if key[0] == 'NAVETTE':
            return []

        meta = reg.trainlines.get(key)
        assert(meta is not None)
        props['color'] = '#' + meta.color
        props['logo'] = meta.logo
        props['trainline'] = Registry.formatKey(key)
        props['line-offset'] = {
            "J": 1,
            "N": 1,
            "R": 1,
            "P": 1,
            "K": 1,
            "L": -1,
            "U": -1,
            "H": -1,
        }.get(props['indice_lig'], 0)
        return [props]

    return filterGeojsonProperties(traces, filterProperties)

#---------------------------------------------

def generateCommunes(communes):
    def filterProperties(props):
        return [{
            "nom": props["nom_officiel_commune_arrondissement_municipal"],
            "code": props["codgeo"],
            "population": props["p20_pop"],
            "superficie": props["superf"], # en km2
            "center": json.loads(props["geo_point"]) if type(props["geo_point"]) == str else props["geo_point"],
        }]

    return filterGeojsonProperties(communes, filterProperties)

#---------------------------------------------

def generateConversionFromMemoryParis(memory_paris, new_stations):
    lut = {}
    for feature in new_stations["features"]:
        props = feature["properties"]
        name = props["nom_zdc"]
        id = props["id_gares"]
        lut[name] = id

    conversion_table = {}
    for feature in memory_paris["features"]:
        props = feature["properties"]
        memory_paris_id = props["id"]
        memory_paris_name = props["name"]
        match = lut.get(memory_paris_name)
        if match is None:
            print(f"WARNING! Station non trouvée: '{memory_paris_name}'. Elle ne sera pas importée depuis Memory pour Paris.")
        else:
            conversion_table[memory_paris_id] = match


    return conversion_table

#---------------------------------------------

if __name__ == '__main__':
    main()
