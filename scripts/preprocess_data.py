from pathlib import Path
import json
from dataclasses import dataclass, field
from typing import List, Dict
from urllib.request import urlretrieve

#---------------------------------------------

def main():
	traces = loadData("traces-du-reseau-ferre-idf.geojson")
	stations = loadData("emplacement-des-gares-idf.geojson")

	reg = buildRegistry(traces, stations)
	#reg.prettyPrint()

	reg = downloadImages(reg)

	new_stations = generateNewStations(stations, reg)
	exportData(new_stations, "memory-pour-idf-stations.geojson")

	new_traces = generateNewTraces(traces, reg)
	exportData(new_traces, "memory-pour-idf-trainline-traces.geojson")

	station_metadata = generateStationMetadata(reg)
	exportData(station_metadata, "memory-pour-idf-stations-metadata.geojson")


#---------------------------------------------

DATA_ROOT = Path(__file__).parent.parent.joinpath("data")

def loadData(filename):
	with open(DATA_ROOT.joinpath("raw", filename)) as f:
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

StationKey = str

@dataclass
class Registry:
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
		id = props['id_gares']
		name = props['nom_zdc']
		entry = reg.connected_stations.get(name, RegistryStationEntry())
		entry.ids.append(id)
		reg.connected_stations[name] = entry

		picto = props['picto']
		if picto is not None:
			name = picto['filename']
			url = f"https://data.iledefrance-mobilites.fr/explore/dataset/emplacement-des-gares-idf/files/{picto['id']}/download/"
			key = Registry.makeKeyFromStationProps(props)
			reg.trainlines[key].logo_svg_url = url
			reg.trainlines[key].logo_filename = name

	return reg

#---------------------------------------------

def downloadImages(reg):
	for key, entry in reg.trainlines.items():
		if entry.logo_svg_url is not None:
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

def generateStationMetadata(reg):
	return {
		"connected-stations": {
			id: connected.ids
			for connected in reg.connected_stations.values()
			if len(connected.ids) > 1
			for id in connected.ids
		}
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

def generateNewStations(stations, reg):
	def filterEntry(props):
		return props["mode"] != 'TER'

	def filterProperties(props):
		if props["mode"] == 'TER':
			return []

		key = Registry.makeKeyFromStationProps(props)
		meta = reg.trainlines.get(key)
		assert(meta is not None)
		props['color'] = '#' + meta.color
		props['logo'] = "data/images/" + meta.logo_filename
		return [props]

	return filterGeojsonProperties(stations, filterProperties)

#---------------------------------------------

def generateNewTraces(traces, reg):
	def filterProperties(props):
		if props["mode"] == 'TER':
			return []

		key = Registry.makeKeyFromTraceProps(props)
		meta = reg.trainlines.get(key)
		assert(meta is not None)
		props['color'] = '#' + meta.color
		props['logo'] = meta.logo
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

if __name__ == '__main__':
	main()
