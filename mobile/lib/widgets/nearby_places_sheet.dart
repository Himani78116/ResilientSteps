import 'package:flutter/material.dart';

import '../models/nearby_place.dart';

class NearbyPlacesSheet extends StatelessWidget {
  const NearbyPlacesSheet({
    super.key,
    required this.category,
    required this.places,
    required this.onPlaceSelected,
  });

  final NearbyCategory category;
  final List<NearbyPlace> places;
  final ValueChanged<NearbyPlace> onPlaceSelected;

  bool get _grouped {
    final List<NearbyAnchor?> anchors = places
        .map((NearbyPlace place) => place.anchor)
        .toList(growable: false);
    return anchors.any((NearbyAnchor? anchor) => anchor != null);
  }

  List<NearbyPlace> _placesFor(NearbyAnchor anchor) =>
      places
          .where((NearbyPlace place) => place.anchor == anchor)
          .toList(growable: false)..sort(
          (NearbyPlace a, NearbyPlace b) =>
              a.distanceMeters.compareTo(b.distanceMeters),
        );

  @override
  Widget build(BuildContext context) {
    final List<Widget> children = <Widget>[
      Text(
        category.label,
        style: Theme.of(
          context,
        ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 8),
    ];

    if (places.isEmpty) {
      children.add(
        const Padding(
          padding: EdgeInsets.only(top: 16, bottom: 24),
          child: Text(
            'No places found within 3 km of your route endpoints.',
          ),
        ),
      );
    } else if (_grouped) {
      children.add(
        _buildSection(
          context,
          NearbyAnchor.routeStart,
          'Places around your start point',
        ),
      );
      children.add(
        _buildSection(
          context,
          NearbyAnchor.routeEnd,
          'Places around your destination',
        ),
      );
    } else {
      children.add(_buildSectionList(context, places));
    }

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: children,
        ),
      ),
    );
  }

  Widget _buildSection(
    BuildContext context,
    NearbyAnchor anchor,
    String title,
  ) {
    final List<NearbyPlace> anchorPlaces = _placesFor(anchor);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          title,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
            color: const Color(0xFF2F6EF6),
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(height: 4),
        if (anchorPlaces.isEmpty)
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Text('No places found within 3 km.'),
          )
        else
          _buildSectionList(context, anchorPlaces),
      ],
    );
  }

  Widget _buildSectionList(
    BuildContext context,
    List<NearbyPlace> anchorPlaces,
  ) {
    return Flexible(
      child: ListView.separated(
        shrinkWrap: true,
        itemCount: anchorPlaces.length,
        separatorBuilder: (_, _) => const Divider(height: 1),
        itemBuilder: (BuildContext context, int index) {
          final NearbyPlace place = anchorPlaces[index];
          return ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(_iconFor(category)),
            title: Text(place.name),
            subtitle: Text(
              '${_distanceLabel(place.distanceMeters)}'
              '${place.address == null ? '' : '\n${place.address}'}',
            ),
            isThreeLine: place.address != null,
            trailing: const Icon(Icons.directions_walk_rounded),
            onTap: () => onPlaceSelected(place),
          );
        },
      ),
    );
  }

  static String _distanceLabel(int meters) => meters < 1000
      ? '$meters m away'
      : '${(meters / 1000).toStringAsFixed(1)} km away';

  static IconData _iconFor(NearbyCategory category) {
    switch (category) {
      case NearbyCategory.hospital:
        return Icons.local_hospital_rounded;
      case NearbyCategory.police:
        return Icons.local_police_rounded;
      case NearbyCategory.metro:
        return Icons.subway_rounded;
      case NearbyCategory.bus:
        return Icons.directions_bus_rounded;
    }
  }
}
