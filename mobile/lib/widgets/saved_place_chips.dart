import 'package:flutter/material.dart';

import '../screens/saved_places_screen.dart';
import '../services/saved_places_service.dart';

class SavedPlaceChips extends StatefulWidget {
  const SavedPlaceChips({
    super.key,
    required this.onPlaceSelected,
  });

  final Future<void> Function(double lat, double lon, String name)
      onPlaceSelected;

  @override
  State<SavedPlaceChips> createState() => _SavedPlaceChipsState();
}

class _SavedPlaceChipsState extends State<SavedPlaceChips> {
  List<SavedPlace> _places = <SavedPlace>[];

  @override
  void initState() {
    super.initState();
    _refreshPlaces();
  }

  void _refreshPlaces() {
    _places = SavedPlacesService.instance.getCachedPlaces();
  }

  Future<void> _openManageScreen() async {
    final SavedPlace? result = await Navigator.push<SavedPlace>(
      context,
      MaterialPageRoute<SavedPlace>(
        builder: (_) => const SavedPlacesScreen(),
      ),
    );

    if (result != null && mounted) {
      await widget.onPlaceSelected(
        result.lat,
        result.lon,
        result.displayName,
      );
    }

    if (!mounted) {
      return;
    }

    setState(_refreshPlaces);
  }

  @override
  Widget build(BuildContext context) {
    if (_places.isEmpty) {
      return const SizedBox.shrink();
    }

    return SizedBox(
      height: 36,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: _places.length + 1,
        separatorBuilder: (BuildContext context, int index) =>
            const SizedBox(width: 8),
        itemBuilder: (BuildContext context, int index) {
          if (index == _places.length) {
            return ActionChip(
              avatar: const Icon(Icons.edit_outlined, size: 16),
              label: const Text('Manage'),
              onPressed: _openManageScreen,
            );
          }

          final SavedPlace place = _places[index];
          return ActionChip(
            label: Text(place.label),
            onPressed: () async {
              await widget.onPlaceSelected(
                place.lat,
                place.lon,
                place.displayName,
              );
            },
          );
        },
      ),
    );
  }
}
