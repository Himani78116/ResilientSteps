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

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              category.label,
              style: Theme.of(
                context,
              ).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            if (places.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Text('No places found within 3 km.'),
              )
            else
              Flexible(
                child: ListView.separated(
                  shrinkWrap: true,
                  itemCount: places.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (BuildContext context, int index) {
                    final NearbyPlace place = places[index];
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
              ),
          ],
        ),
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
