from pathlib import Path
import json
from dataclasses import dataclass, field
from typing import List, Dict

#---------------------------------------------

def main():
	traces = loadData("traces-du-reseau-ferre-idf.geojson")
	stations = loadData("emplacement-des-gares-idf.geojson")

	reg = buildRegistry(traces, stations)
	reg.prettyPrint()

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
		if mode == 'TER' and line == 'C':
			mode = 'RER'
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
		key = props['nom_zdc']
		entry = reg.connected_stations.get(key, RegistryStationEntry())
		entry.ids.append(id)
		reg.connected_stations[key] = entry

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
		props['logo'] = meta.logo
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
