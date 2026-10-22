import 'package:flutter/material.dart';

import '../models/nearby_place.dart';
import 'navigation_card.dart';

/// Shown when the user taps a Nearby-place badge on the home map: lets
/// them pick which facility category to look for around that anchor point.
class NearbyCategoryPickerSheet extends StatelessWidget {
  const NearbyCategoryPickerSheet({
    super.key,
    required this.title,
    required this.isLoading,
    required this.onCategorySelected,
  });

  final String title;
  final bool isLoading;
  final ValueChanged<NearbyCategory> onCategorySelected;

  @override
  Widget build(BuildContext context) {
    final List<Widget> children = <Widget>[
      Text(
        title,
        style: Theme.of(
          context,
        ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 4),
      Text(
        'Which places do you want to see?',
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
          color: const Color(0xFF54657A),
        ),
      ),
      const SizedBox(height: 12),
    ];

    if (isLoading) {
      children.add(
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 24),
          child: Center(child: CircularProgressIndicator(strokeWidth: 2.4)),
        ),
      );
    } else {
      children.add(
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: <Widget>[
            // Only the four concrete facility types: the fetch-everything
            // "Nearby" entry point was removed from both the HUD and this
            // picker, so badge taps are categorically explicit.
            for (final NearbyCategory category in NearbyCategory.values)
              if (category != NearbyCategory.all)
                NearbyCategoryChip(
                  category: category,
                  isSelected: false,
                  isLoading: false,
                  onTap: onCategorySelected,
                ),
          ],
        ),
      );
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
}

/// Shown after a nearby-places fetch completes. When every category was
/// requested the list is bifurcated by facility type within each anchor
/// section, so the user browses Police / Hospitals / Metro / Bus together.
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

  static const List<NearbyCategory> _displayOrder = <NearbyCategory>[
    NearbyCategory.police,
    NearbyCategory.hospital,
    NearbyCategory.metro,
    NearbyCategory.bus,
  ];

  bool get _grouped {
    final List<NearbyAnchor?> anchors = places
        .map((NearbyPlace place) => place.anchor)
        .toList(growable: false);
    return anchors.any((NearbyAnchor? anchor) => anchor != null);
  }

  bool get _bifurcateByCategory {
    if (category == NearbyCategory.all) {
      return true;
    }
    final Set<NearbyCategory> seen = places
        .map((NearbyPlace place) => place.category)
        .toSet();
    return seen.length > 1;
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
          child: Text('No places found within 3 km.'),
        ),
      );
    } else if (_grouped) {
      // A badge fetch sets one anchor only; render the requested section(s)
      // and never the empty placeholder for the anchor nobody asked about.
      final Map<NearbyAnchor, String> sectionTitles =
          <NearbyAnchor, String>{
        NearbyAnchor.routeStart: 'Places around your start point',
        NearbyAnchor.routeEnd: 'Places around your destination',
      };
      for (final MapEntry<NearbyAnchor, String> entry
          in sectionTitles.entries) {
        if (places.any((NearbyPlace place) => place.anchor == entry.key)) {
          children.add(_buildAnchorSection(context, entry.key, entry.value));
        }
      }
    } else {
      children.add(
        _buildPlacesForAnchor(
          context,
          places,
          bifurcate: _bifurcateByCategory,
        ),
      );
    }

    return SafeArea(
      child: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: children,
          ),
        ),
      ),
    );
  }

  Widget _buildAnchorSection(
    BuildContext context,
    NearbyAnchor anchor,
    String title,
  ) {
    // Callers only enter here when the anchor has at least one place, so the
    // empty placeholder from the double-section layout is gone for good.
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
        _buildPlacesForAnchor(
          context,
          anchorPlaces,
          bifurcate: _bifurcateByCategory,
        ),
      ],
    );
  }

  Widget _buildPlacesForAnchor(
    BuildContext context,
    List<NearbyPlace> anchorPlaces, {
    required bool bifurcate,
  }) {
    if (!bifurcate) {
      return _buildSectionList(context, anchorPlaces);
    }
    final List<Widget> children = <Widget>[];
    for (final NearbyCategory type in _displayOrder) {
      final List<NearbyPlace> bucket = anchorPlaces
          .where((NearbyPlace place) => place.category == type)
          .toList(growable: false);
      if (bucket.isEmpty) {
        continue;
      }
      children.add(
        Padding(
          padding: const EdgeInsets.only(top: 8, bottom: 2),
          child: Text(
            type.shortLabel,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: const Color(0xFF54657A),
              fontWeight: FontWeight.w800,
              letterSpacing: 0.4,
            ),
          ),
        ),
      );
      children.add(_buildSectionList(context, bucket));
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }

  Widget _buildSectionList(
    BuildContext context,
    List<NearbyPlace> anchorPlaces,
  ) {
    return ListView.separated(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: anchorPlaces.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (BuildContext context, int index) {
        final NearbyPlace place = anchorPlaces[index];
        return ListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          leading: Icon(_iconFor(place.category)),
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
    );
  }

  static String _distanceLabel(int meters) => meters < 1000
      ? '$meters m away'
      : '${(meters / 1000).toStringAsFixed(1)} km away';

  static IconData _iconFor(NearbyCategory category) {
    switch (category) {
      case NearbyCategory.all:
        return Icons.near_me_rounded;
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
