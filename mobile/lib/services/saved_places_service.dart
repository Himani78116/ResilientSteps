import 'dart:convert';

import 'package:hive_flutter/hive_flutter.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'auth_service.dart';

class SavedPlace {
  const SavedPlace({
    this.id,
    required this.label,
    required this.displayName,
    required this.lat,
    required this.lon,
  });

  final int? id;
  final String label;
  final String displayName;
  final double lat;
  final double lon;

  Map<String, dynamic> toJson() => <String, dynamic>{
    if (id != null) 'id': id,
    'label': label,
    'display_name': displayName,
    'lat': lat,
    'lon': lon,
  };

  factory SavedPlace.fromJson(Map<String, dynamic> json) => SavedPlace(
    id: json['id'] as int?,
    label: json['label'] as String,
    displayName: json['display_name'] as String,
    lat: (json['lat'] as num).toDouble(),
    lon: (json['lon'] as num).toDouble(),
  );
}

class SavedPlacesService {
  SavedPlacesService._();

  static final SavedPlacesService instance = SavedPlacesService._();

  static const String _boxName = 'walksafe_saved_places';
  static const String _key = 'places_v1';

  SupabaseClient get _supabase => Supabase.instance.client;

  /// Returns places from Supabase, falling back to cache on network failure.
  Future<List<SavedPlace>> getPlaces() async {
    if (!AuthService.instance.isLoggedIn) {
      return <SavedPlace>[];
    }

    try {
      final List<SavedPlace> remote = await _fetchFromSupabase();
      await _writeCache(remote);
      return remote;
    } catch (_) {
      return _readCache();
    }
  }

  /// Instant cache read, safe to call synchronously.
  List<SavedPlace> getCachedPlaces() {
    if (!AuthService.instance.isLoggedIn) {
      return <SavedPlace>[];
    }
    return _readCache();
  }

  Future<SavedPlace> addPlace(SavedPlace place) async {
    final String userId = AuthService.instance.currentUser!.id;
    final Map<String, dynamic> response = await _supabase
        .from('saved_places')
        .insert(<String, dynamic>{
          'user_id': userId,
          'label': place.label,
          'display_name': place.displayName,
          'lat': place.lat,
          'lon': place.lon,
        })
        .select()
        .single();

    final SavedPlace saved = SavedPlace.fromJson(response);
    await _writeCache(<SavedPlace>[..._readCache(), saved]);
    return saved;
  }

  Future<void> deletePlace(int id) async {
    await _supabase.from('saved_places').delete().eq('id', id);
    await _writeCache(
      _readCache().where((SavedPlace place) => place.id != id).toList(),
    );
  }

  Future<void> syncFromSupabase() async {
    if (!AuthService.instance.isLoggedIn) {
      return;
    }

    final List<SavedPlace> remote = await _fetchFromSupabase();
    await _writeCache(remote);
  }

  Future<void> clearLocalCache() async {
    final Box<dynamic> box = await Hive.openBox(_boxName);
    await box.delete(_key);
  }

  Future<List<SavedPlace>> _fetchFromSupabase() async {
    final List<dynamic> response = await _supabase
        .from('saved_places')
        .select()
        .order('created_at', ascending: true);

    return response
        .map(
          (dynamic entry) =>
              SavedPlace.fromJson(Map<String, dynamic>.from(entry as Map)),
        )
        .toList();
  }

  List<SavedPlace> _readCache() {
    try {
      final Box<dynamic> box = Hive.box(_boxName);
      final Object? raw = box.get(_key);
      if (raw == null) {
        return <SavedPlace>[];
      }

      return (jsonDecode(raw as String) as List<dynamic>)
          .map(
            (dynamic entry) => SavedPlace.fromJson(
              Map<String, dynamic>.from(entry as Map),
            ),
          )
          .toList();
    } catch (_) {
      return <SavedPlace>[];
    }
  }

  Future<void> _writeCache(List<SavedPlace> places) async {
    final Box<dynamic> box = await Hive.openBox(_boxName);
    await box.put(
      _key,
      jsonEncode(places.map((SavedPlace place) => place.toJson()).toList()),
    );
  }
}
