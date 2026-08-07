import 'dart:async';

import 'package:flutter/material.dart';

import '../models/place_suggestion.dart';
import '../services/place_search_service.dart';

class DestinationSearchScreen extends StatefulWidget {
  const DestinationSearchScreen({
    super.key,
    required this.placeSearchService,
    this.initialQuery,
  });

  final PlaceSearchService placeSearchService;
  final String? initialQuery;

  @override
  State<DestinationSearchScreen> createState() =>
      _DestinationSearchScreenState();
}

class _DestinationSearchScreenState extends State<DestinationSearchScreen> {
  late final TextEditingController _controller;
  Timer? _debounce;
  List<PlaceSuggestion> _results = const <PlaceSuggestion>[];
  bool _isLoading = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialQuery ?? '');
    if (_controller.text.trim().length >= 2) {
      _search();
    }
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onQueryChanged(String value) {
    _debounce?.cancel();
    final String trimmed = value.trim();
    if (trimmed.length < 2) {
      setState(() {
        _results = const <PlaceSuggestion>[];
        _errorMessage = null;
        _isLoading = false;
      });
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 350), _search);
  }

  Future<void> _search() async {
    final String query = _controller.text.trim();
    if (query.length < 2) {
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final List<PlaceSuggestion> results = await widget.placeSearchService
          .searchDestinations(query);
      if (!mounted) {
        return;
      }
      setState(() {
        _results = results;
        _isLoading = false;
        _errorMessage = results.isEmpty
            ? 'No nearby matches. Try a landmark, neighborhood, or road name.'
            : null;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _results = const <PlaceSuggestion>[];
        _isLoading = false;
        _errorMessage =
            'Search is unavailable right now. You can still go back and drop a pin on the map.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Choose destination'),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              TextField(
                controller: _controller,
                autofocus: true,
                textInputAction: TextInputAction.search,
                onChanged: _onQueryChanged,
                onSubmitted: (_) => _search(),
                decoration: InputDecoration(
                  hintText: 'Search for a road, landmark, or area',
                  filled: true,
                  fillColor: Colors.white,
                  prefixIcon: const Icon(Icons.search_rounded),
                  suffixIcon: _isLoading
                      ? const Padding(
                          padding: EdgeInsets.all(14),
                          child: SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2.2),
                          ),
                        )
                      : _controller.text.trim().isEmpty
                      ? null
                      : IconButton(
                          onPressed: () {
                            _controller.clear();
                            _onQueryChanged('');
                          },
                          icon: const Icon(Icons.close_rounded),
                        ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(18),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 14),
              Text(
                'Popular landmarks work best. You can also go back and tap directly on the map.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: const Color(0xFF5A6C68),
                ),
              ),
              const SizedBox(height: 16),
              Expanded(
                child: _buildResults(theme),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildResults(ThemeData theme) {
    if (_errorMessage != null) {
      return _MessageCard(
        icon: Icons.travel_explore_rounded,
        message: _errorMessage!,
      );
    }

    if (_results.isEmpty) {
      return const _MessageCard(
        icon: Icons.place_outlined,
        message:
            'Search for places like Pune Station, FC Road, or Shaniwar Wada.',
      );
    }

    return ListView.separated(
      itemCount: _results.length,
      separatorBuilder: (_, _) => const SizedBox(height: 10),
      itemBuilder: (BuildContext context, int index) {
        final PlaceSuggestion suggestion = _results[index];
        return Material(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
          child: InkWell(
            borderRadius: BorderRadius.circular(18),
            onTap: () => Navigator.of(context).pop(suggestion),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: const Color(0xFFE4F2ED),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(
                      Icons.near_me_rounded,
                      color: Color(0xFF0F6B63),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          suggestion.title,
                          style: theme.textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                            color: const Color(0xFF16312D),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          suggestion.subtitle,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: const Color(0xFF5C6B67),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: const Color(0xFFE7F2EF),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: const Color(0xFF0F6B63)),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Text(
              message,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: const Color(0xFF4C5F5B),
                height: 1.35,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
