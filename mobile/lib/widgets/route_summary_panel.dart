import 'package:flutter/material.dart';

import '../models/route_segment_safety.dart';
import '../models/scored_route.dart';

class RouteSummaryPanel extends StatelessWidget {
  const RouteSummaryPanel({
    super.key,
    required this.route,
    required this.isLoading,
    required this.destinationLabel,
    required this.onClearRoute,
  });

  final ScoredRoute? route;
  final bool isLoading;
  final String? destinationLabel;
  final VoidCallback onClearRoute;

  @override
  Widget build(BuildContext context) {
    if (!isLoading && route == null) {
      return const SizedBox.shrink();
    }

    if (isLoading) {
      return _PanelShell(
        child: Row(
          children: <Widget>[
            const SizedBox(
              width: 26,
              height: 26,
              child: CircularProgressIndicator(strokeWidth: 2.6),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Text(
                    'Finding the safer route...',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                      color: const Color(0xFF16312D),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Checking nearby streets and recent safety signals.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: const Color(0xFF5A6C68),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    final _RouteInsights insights = _RouteInsights.fromRoute(route!);

    return _PanelShell(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              _ScoreChip(score: route!.averageSafetyScore, color: insights.toneColor),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      destinationLabel ?? 'Pinned destination',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w800,
                        color: const Color(0xFF16312D),
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      insights.headline,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: const Color(0xFF405A54),
                        height: 1.3,
                      ),
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Clear route',
                onPressed: onClearRoute,
                icon: const Icon(Icons.close_rounded),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: <Widget>[
              Expanded(
                child: _MetricPill(
                  icon: Icons.timelapse_rounded,
                  label: 'Walk',
                  value: insights.etaLabel,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _MetricPill(
                  icon: Icons.route_rounded,
                  label: 'Distance',
                  value: insights.distanceLabel,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: _MetricPill(
                  icon: Icons.visibility_rounded,
                  label: 'Watch-outs',
                  value: insights.watchOutLabel,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            insights.advice,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: const Color(0xFF5A6C68),
              height: 1.35,
            ),
          ),
        ],
      ),
    );
  }
}

class _PanelShell extends StatelessWidget {
  const _PanelShell({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(24),
        boxShadow: const <BoxShadow>[
          BoxShadow(
            color: Color(0x1A18302B),
            blurRadius: 18,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
        child: child,
      ),
    );
  }
}

class _ScoreChip extends StatelessWidget {
  const _ScoreChip({required this.score, required this.color});

  final double score;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: <Color>[color, color.withValues(alpha: 0.72)],
        ),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        children: <Widget>[
          Text(
            score.toStringAsFixed(0),
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
            ),
          ),
          Text(
            'score',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: Colors.white.withValues(alpha: 0.90),
            ),
          ),
        ],
      ),
    );
  }
}

class _MetricPill extends StatelessWidget {
  const _MetricPill({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFFF4F6F2),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: <Widget>[
          Icon(icon, size: 18, color: const Color(0xFF4A645E)),
          const SizedBox(height: 6),
          Text(
            label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: const Color(0xFF6A7A76),
            ),
          ),
          const SizedBox(height: 2),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
              fontWeight: FontWeight.w800,
              color: const Color(0xFF16312D),
            ),
          ),
        ],
      ),
    );
  }
}

class _RouteInsights {
  const _RouteInsights({
    required this.headline,
    required this.distanceLabel,
    required this.etaLabel,
    required this.watchOutLabel,
    required this.advice,
    required this.toneColor,
  });

  final String headline;
  final String distanceLabel;
  final String etaLabel;
  final String watchOutLabel;
  final String advice;
  final Color toneColor;

  factory _RouteInsights.fromRoute(ScoredRoute route) {
    final double score = route.averageSafetyScore;
    final int riskySegments = route.segments
        .where((RouteSegmentSafety segment) => _segmentTier(segment) == _Tier.risky)
        .length;
    final int cautiousSegments = route.segments
        .where((RouteSegmentSafety segment) => _segmentTier(segment) == _Tier.cautious)
        .length;
    final int etaMinutes = (route.totalDistanceMeters / 75).clamp(1, 180).round();

    final Color toneColor;
    final String headline;
    if (score >= 75) {
      toneColor = const Color(0xFF2C8C63);
      headline = 'Steadier route';
    } else if (score >= 55) {
      toneColor = const Color(0xFFD09A20);
      headline = 'Mostly okay, with some caution';
    } else {
      toneColor = const Color(0xFFBF4F41);
      headline = 'Stay extra alert on this route';
    }

    return _RouteInsights(
      headline: headline,
      distanceLabel: _formatDistance(route.totalDistanceMeters),
      etaLabel: '$etaMinutes min',
      watchOutLabel: _watchOutLabel(
        riskySegments: riskySegments,
        cautiousSegments: cautiousSegments,
      ),
      advice: _buildAdvice(
        riskySegments: riskySegments,
        cautiousSegments: cautiousSegments,
      ),
      toneColor: toneColor,
    );
  }

  static _Tier _segmentTier(RouteSegmentSafety segment) {
    final String normalizedLevel = (segment.safetyLevel ?? '').toUpperCase();
    if (normalizedLevel == 'RISKY') {
      return _Tier.risky;
    }
    if (normalizedLevel == 'CAUTIOUS') {
      return _Tier.cautious;
    }
    if (segment.safetyScore < 40) {
      return _Tier.risky;
    }
    if (segment.safetyScore < 70) {
      return _Tier.cautious;
    }
    return _Tier.safe;
  }

  static String _watchOutLabel({
    required int riskySegments,
    required int cautiousSegments,
  }) {
    if (riskySegments > 0) {
      return 'High';
    }
    if (cautiousSegments >= 10) {
      return 'Moderate';
    }
    if (cautiousSegments > 0) {
      return 'Low';
    }
    return 'Minimal';
  }

  static String _buildAdvice({
    required int riskySegments,
    required int cautiousSegments,
  }) {
    if (riskySegments > 0) {
      return 'Keep to brighter roads and stay alert near quieter stretches.';
    }
    if (cautiousSegments > 0) {
      return 'A few stretches need extra attention, especially after dark.';
    }
    return 'This route stays on the calmer side right now.';
  }

  static String _formatDistance(double meters) {
    if (meters >= 1000) {
      return '${(meters / 1000).toStringAsFixed(1)} km';
    }
    return '${meters.round()} m';
  }
}

enum _Tier { safe, cautious, risky }
