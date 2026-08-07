# import osmnx as ox

# place = "Pune, Maharashtra, India"
# graph = ox.graph_from_place(place, network_type="walk")

# # restrict to 5km bounding box
# center = (18.5204, 73.8567)
# graph = ox.graph_from_point(center, dist=2500, network_type="walk")

# nodes, edges = ox.graph_to_gdfs(graph)

import osmnx as ox
ox.settings.log_console = True
ox.settings.use_cache = True
center = (18.5204, 73.8567)  # Pune center
graph = ox.graph_from_point(center, dist=2500, network_type="walk")

nodes, edges = ox.graph_to_gdfs(graph)

ox.plot_graph(graph)