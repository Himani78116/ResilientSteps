import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';

import '../controllers/navigation_controller.dart';
import '../models/scored_route.dart';
import '../models/safety_zone.dart';
import '../screens/report_incident_screen.dart';
import 'safety_zone_overlay.dart';
import 'walksafe_map_view.dart';
import 'gradient_button.dart';
import 'route_info_card.dart';

class NavigationCard extends StatefulWidget {
  const NavigationCard({
    super.key,
    required this.navState,
    required this.route,
    required this.destinationLabel,
    required this.isLoadingRoute,
    required this.isRerouting,
    required this.onStartNavigation,
    required this.onStopNavigation,
    required this.onDismissArrival,
    this.onExpansionChanged,
  });

  final NavigationState navState;
  final ScoredRoute? route;
  final String? destinationLabel;
  final bool isLoadingRoute;
  final bool isRerouting;
  final VoidCallback onStartNavigation;
  final VoidCallback onStopNavigation;
  final VoidCallback onDismissArrival;
  final ValueChanged<bool>? onExpansionChanged;

  @override
  State<NavigationCard> createState() => _NavigationCardState();
}

class _NavigationCardState extends State<NavigationCard> {
  bool _cardExpanded = false;

  @override
  void didUpdateWidget(covariant NavigationCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.navState != NavigationState.active &&
        oldWidget.navState == NavigationState.active) {
      _setExpanded(false);
    }
    if (widget.route == null && _cardExpanded) {
      _setExpanded(false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (widget.isLoadingRoute && widget.route == null) {
      return Align(
        key: const ValueKey<String>('route-loading'),
        alignment: Alignment.bottomCenter,
        child: RouteInfoCard(
          route: widget.route,
          isLoading: true,
          destinationLabel: widget.destinationLabel,
          buttonLabel: 'START NAVIGATION',
          onPrimaryPressed: null,
        ),
      );
    }

    if (widget.navState == NavigationState.planning && widget.route != null) {
      return Align(
        key: const ValueKey<String>('route-planning'),
        alignment: Alignment.bottomCenter,
        child: RouteInfoCard(
          route: widget.route,
          isLoading: false,
          destinationLabel: widget.destinationLabel,
          buttonLabel: 'START NAVIGATION',
          onPrimaryPressed: widget.onStartNavigation,
        ),
      );
    }

    if (widget.navState == NavigationState.active && widget.route != null) {
      return Align(
        key: ValueKey<String>(
          _cardExpanded ? 'route-active-expanded' : 'route-active-collapsed',
        ),
        alignment: Alignment.bottomCenter,
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 220),
          switchInCurve: Curves.easeOutCubic,
          switchOutCurve: Curves.easeInCubic,
          child: _cardExpanded
              ? _buildExpandedNavigationCard(context, widget.route!)
              : _buildCollapsedNavigationStrip(context, widget.route!),
        ),
      );
    }

    if (widget.navState == NavigationState.arrived) {
      return Align(
        key: const ValueKey<String>('route-arrived'),
        alignment: Alignment.bottomCenter,
        child: _buildArrivalCard(context),
      );
    }

    return const SizedBox.shrink(key: ValueKey<String>('route-empty'));
  }

  void _setExpanded(bool value) {
    if (_cardExpanded == value) {
      return;
    }

    setState(() {
      _cardExpanded = value;
    });
    widget.onExpansionChanged?.call(value);
  }

  Widget _buildBottomCardShell({
    required Widget child,
    EdgeInsetsGeometry padding = const EdgeInsets.fromLTRB(22, 22, 22, 22),
    BorderRadius borderRadius = const BorderRadius.all(Radius.circular(32)),
  }) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 560),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.96),
          borderRadius: borderRadius,
          border: Border.all(color: const Color(0xFFF0F4FA)),
          boxShadow: <BoxShadow>[
            BoxShadow(
              color: const Color(0xFF12366E).withValues(alpha: 0.10),
              blurRadius: 36,
              offset: const Offset(0, 18),
            ),
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04),
              blurRadius: 8,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Padding(padding: padding, child: child),
      ),
    );
  }

  Widget _buildCollapsedNavigationStrip(
    BuildContext context,
    ScoredRoute route,
  ) {
    final int etaMinutes = _routeEtaMinutes(route);
    final int safetyScore = _routeSafetyPercent(route);
    final double distKm = route.totalDistanceMeters / 1000;
    final String distLabel = distKm >= 1
        ? '${distKm.toStringAsFixed(1)} km'
        : '${route.totalDistanceMeters.round()} m';

    // Derive shade from average lighting level (0–1 → %)
    final double avgShade = route.segments.isEmpty
        ? 0
        : route.segments
                .map((s) => s.lightingLevel)
                .reduce((a, b) => a + b) /
            route.segments.length;
    final int shadePct = (avgShade * 100).round().clamp(0, 100);

    // ETA clock string
    final DateTime etaTime = DateTime.now().add(Duration(minutes: etaMinutes));
    final String etaStr =
        '${etaTime.hour.toString().padLeft(2, '0')}:${etaTime.minute.toString().padLeft(2, '0')} ${etaTime.hour >= 12 ? 'PM' : 'AM'}';

    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 560),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
          boxShadow: <BoxShadow>[
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.10),
              blurRadius: 32,
              offset: const Offset(0, -8),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Drag handle
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: const Color(0xFFD0D8E4),
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              // Navigation header row
              GestureDetector(
                onTap: () => _setExpanded(true),
                child: Row(
                  children: <Widget>[
                    Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: const Color(0xFF1B6B3A),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(
                        Icons.navigation_rounded,
                        color: Colors.white,
                        size: 22,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          Row(
                            children: <Widget>[
                              Text(
                                'Navigating',
                                style: Theme.of(context)
                                    .textTheme
                                    .titleMedium
                                    ?.copyWith(
                                      color: const Color(0xFF0E1B2A),
                                      fontWeight: FontWeight.w800,
                                    ),
                              ),
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(
                                  horizontal: 8,
                                  vertical: 3,
                                ),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFDCF5E8),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: Text(
                                  'CLIMATE SAFE',
                                  style: Theme.of(context)
                                      .textTheme
                                      .labelSmall
                                      ?.copyWith(
                                        color: const Color(0xFF1B6B3A),
                                        fontWeight: FontWeight.w800,
                                        letterSpacing: 0.4,
                                      ),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 3),
                          Text(
                            '$etaMinutes min  •  $distLabel  •  ETA $etaStr',
                            style: Theme.of(context)
                                .textTheme
                                .bodySmall
                                ?.copyWith(
                                  color: const Color(0xFF5E6D80),
                                  fontWeight: FontWeight.w500,
                                ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(
                      Icons.keyboard_arrow_up_rounded,
                      color: Color(0xFF8A9BB0),
                      size: 24,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              // Three metric cards
              Row(
                children: <Widget>[
                  Expanded(
                    child: _NavMetricCard(
                      label: 'Shade',
                      value: '$shadePct%',
                      sublabel: 'Tree canopy',
                      labelColor: const Color(0xFF1B6B3A),
                      backgroundColor: const Color(0xFFE8F5EE),
                    ),
                  ),
                  const SizedBox(width: 10),
                  const Expanded(
                    child: _NavMetricCard(
                      label: 'Heat Index',
                      value: 'Moderate',
                      sublabel: 'Shade-aware route',
                      labelColor: Color(0xFFC05E0A),
                      backgroundColor: Color(0xFFFFF8E1),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _NavMetricCard(
                      label: 'Safety',
                      value: '$safetyScore / 100',
                      sublabel: 'Pedestrian zone',
                      labelColor: const Color(0xFF1E4EC8),
                      backgroundColor: const Color(0xFFE3EEFF),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              // Route selector chips
              Row(
                children: <Widget>[
                  _RouteChip(
                    label: 'Climate-Smart  •  $etaMinutes min',
                    selected: true,
                    onTap: () {},
                  ),
                  const SizedBox(width: 10),
                  _RouteChip(
                    label: 'Fastest  •  ${(etaMinutes * 0.85).round()} min',
                    selected: false,
                    onTap: () {},
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildExpandedNavigationCard(BuildContext context, ScoredRoute route) {
    final int etaMinutes = _routeEtaMinutes(route);
    final int safetyScore = _routeSafetyPercent(route);
    final ThemeData theme = Theme.of(context);

    return _buildBottomCardShell(
      child: Column(
        key: const ValueKey<String>('active-expanded-card'),
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Expanded(
                child: Text(
                  'Active navigation',
                  style: theme.textTheme.titleLarge?.copyWith(
                    color: const Color(0xFF0E1B2A),
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              TextButton(
                onPressed: () => _setExpanded(false),
                child: const Text('Collapse'),
              ),
            ],
          ),
          if (widget.destinationLabel != null &&
              widget.destinationLabel!.trim().isNotEmpty) ...<Widget>[
            Text(
              widget.destinationLabel!,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: const Color(0xFF66768D),
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 18),
          ],
          Row(
            children: <Widget>[
              Expanded(
                child: _NavigationMetric(
                  label: 'Safety score',
                  value: '$safetyScore%',
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _NavigationMetric(
                  label: 'ETA',
                  value: '$etaMinutes min',
                  alignEnd: true,
                ),
              ),
            ],
          ),
          if (widget.isRerouting) ...<Widget>[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: const Color(0x142F6EF6),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.2,
                      color: Color(0xFF2F6EF6),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Text(
                    'Rerouting to keep you on the safest path...',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: const Color(0xFF2F6EF6),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
            ),
          ],
          const SizedBox(height: 16),
          Text(
            _navigationAdvisoryText(route),
            style: theme.textTheme.bodyMedium?.copyWith(
              color: route.warning == null
                  ? const Color(0xFF5E6D80)
                  : const Color(0xFF8B5A14),
              height: 1.35,
              fontWeight: route.warning == null
                  ? FontWeight.w500
                  : FontWeight.w600,
            ),
          ),
          const SizedBox(height: 22),
          GradientButton(
            label: 'STOP NAVIGATION',
            onPressed: widget.onStopNavigation,
            height: 62,
            borderRadius: 24,
            gradient: const LinearGradient(
              colors: <Color>[Color(0xFFE24A3B), Color(0xFFD7644F)],
              begin: Alignment.centerLeft,
              end: Alignment.centerRight,
            ),
            textStyle: theme.textTheme.titleMedium?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildArrivalCard(BuildContext context) {
    final ThemeData theme = Theme.of(context);

    return _buildBottomCardShell(
      child: Column(
        key: const ValueKey<String>('arrival-card'),
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: const Color(0x1730C56A),
                  borderRadius: BorderRadius.circular(18),
                ),
                child: const Icon(
                  Icons.check_circle_rounded,
                  color: Color(0xFF30C56A),
                  size: 30,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      'You have arrived',
                      style: theme.textTheme.titleLarge?.copyWith(
                        color: const Color(0xFF0E1B2A),
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'You are within walking distance of your destination.',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: const Color(0xFF5E6D80),
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 22),
          GradientButton(
            label: 'DONE',
            onPressed: widget.onDismissArrival,
            height: 62,
            borderRadius: 24,
            textStyle: theme.textTheme.titleMedium?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.3,
            ),
          ),
        ],
      ),
    );
  }

  int _routeEtaMinutes(ScoredRoute route) =>
      (route.totalDistanceMeters / 75).clamp(1, 180).round();

  int _routeSafetyPercent(ScoredRoute route) =>
      route.averageSafetyScore.round().clamp(0, 100).toInt();

  String _navigationAdvisoryText(ScoredRoute route) {
    final String? warning = route.warning?.trim();
    if (warning != null && warning.isNotEmpty) {
      return warning;
    }

    final int safetyScore = _routeSafetyPercent(route);
    if (safetyScore >= 75) {
      return 'This route is staying on calmer stretches right now.';
    }
    if (safetyScore >= 55) {
      return 'Stay alert near the highlighted sections as conditions change.';
    }
    return 'Keep to brighter, busier roads and reassess if conditions feel off.';
  }
}

/// A compact pill-style search bar used in the top overlay bar.
class HomeSearchPanel extends StatelessWidget {
  const HomeSearchPanel({
    super.key,
    required this.destinationLabel,
    required this.isLoadingRoute,
    required this.onTap,
    required this.onClear,
  });

  final String? destinationLabel;
  final bool isLoadingRoute;
  final VoidCallback onTap;
  final VoidCallback? onClear;

  @override
  Widget build(BuildContext context) {
    return _GlassPanel(
      borderRadius: 24,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          child: Row(
            children: <Widget>[
              const Icon(
                Icons.search_rounded,
                color: Color(0xFF5E6D80),
                size: 22,
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  destinationLabel ?? 'Finding best walking route...',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: destinationLabel != null
                        ? const Color(0xFF111C2A)
                        : const Color(0xFF8A9BB0),
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              if (isLoadingRoute)
                const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.2,
                    color: Color(0xFF2F6EF6),
                  ),
                )
              else if (onClear != null)
                GestureDetector(
                  onTap: onClear,
                  child: const Icon(
                    Icons.close_rounded,
                    color: Color(0xFF8A9BB0),
                    size: 20,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// The full-screen idle bottom sheet — Screen 1: Search & Plan Offline.
/// Shown when navState == idle and no route is loading.
class WalkSafeBottomSheet extends StatelessWidget {
  const WalkSafeBottomSheet({
    super.key,
    required this.destinationLabel,
    required this.route,
    required this.isLoadingRoute,
    required this.onSearchTap,
    required this.onFindSafeRoute,
    required this.onClearRoute,
  });

  final String? destinationLabel;
  final ScoredRoute? route;
  final bool isLoadingRoute;
  final VoidCallback onSearchTap;
  final VoidCallback onFindSafeRoute;
  final VoidCallback? onClearRoute;

  static const Color _deepGreen = Color(0xFF1B6B3A);
  static const Color _lightGreen = Color(0xFF2E8B50);

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    final bool hasDestination = destinationLabel != null &&
        destinationLabel!.trim().isNotEmpty;

    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 560),
      child: DecoratedBox(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(28)),
          boxShadow: <BoxShadow>[
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.10),
              blurRadius: 32,
              offset: const Offset(0, -8),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              // Drag handle
              Center(
                child: Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: const Color(0xFFD0D8E4),
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
              const SizedBox(height: 18),
              // Search field
              GestureDetector(
                onTap: onSearchTap,
                child: Container(
                  height: 52,
                  decoration: BoxDecoration(
                    color: const Color(0xFFF2F5FA),
                    borderRadius: BorderRadius.circular(26),
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 18),
                  child: Row(
                    children: <Widget>[
                      const Icon(
                        Icons.search_rounded,
                        color: Color(0xFF8A9BB0),
                        size: 22,
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          hasDestination
                              ? destinationLabel!
                              : 'Where do you want to walk?',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: theme.textTheme.bodyLarge?.copyWith(
                            color: hasDestination
                                ? const Color(0xFF111C2A)
                                : const Color(0xFFA0ADBF),
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                      if (isLoadingRoute)
                        const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2.2,
                            color: _deepGreen,
                          ),
                        )
                      else if (onClearRoute != null && hasDestination)
                        GestureDetector(
                          onTap: onClearRoute,
                          child: const Icon(
                            Icons.close_rounded,
                            color: Color(0xFF8A9BB0),
                            size: 20,
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              // Destination result card
              if (hasDestination && !isLoadingRoute) ...<Widget>[
                const SizedBox(height: 14),
                _DestinationResultCard(
                  route: route,
                  destinationLabel: destinationLabel!,
                ),
              ],
              // Weather / heat banner
              const SizedBox(height: 12),
              const _WeatherBanner(),
              const SizedBox(height: 18),
              // Find Safe Route button
              SizedBox(
                width: double.infinity,
                height: 54,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: <Color>[_deepGreen, _lightGreen],
                      begin: Alignment.centerLeft,
                      end: Alignment.centerRight,
                    ),
                    borderRadius: BorderRadius.circular(27),
                    boxShadow: <BoxShadow>[
                      BoxShadow(
                        color: _deepGreen.withValues(alpha: 0.30),
                        blurRadius: 20,
                        offset: const Offset(0, 8),
                      ),
                    ],
                  ),
                  child: Material(
                    type: MaterialType.transparency,
                    child: InkWell(
                      onTap: hasDestination && !isLoadingRoute
                          ? onFindSafeRoute
                          : null,
                      borderRadius: BorderRadius.circular(27),
                      splashColor: Colors.white.withValues(alpha: 0.12),
                      child: Center(
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            const Icon(
                              Icons.arrow_forward_rounded,
                              color: Colors.white,
                              size: 20,
                            ),
                            const SizedBox(width: 10),
                            Text(
                              'Find Safe Route',
                              style: theme.textTheme.titleMedium?.copyWith(
                                color: Colors.white,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 0.2,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DestinationResultCard extends StatelessWidget {
  const _DestinationResultCard({
    required this.destinationLabel,
    required this.route,
  });

  final String destinationLabel;
  final ScoredRoute? route;

  @override
  Widget build(BuildContext context) {
    final ThemeData theme = Theme.of(context);
    String? subtitle;
    if (route != null) {
      final int etaMin = (route!.totalDistanceMeters / 75).clamp(1, 180).round();
      final double distKm = route!.totalDistanceMeters / 1000;
      final String distLabel = distKm >= 1
          ? '${distKm.toStringAsFixed(1)} km'
          : '${route!.totalDistanceMeters.round()} m';
      // Shade derived from average lighting level (0-1 → %)
      final double avgShade = route!.segments.isEmpty
          ? 0
          : route!.segments
                  .map((s) => s.lightingLevel)
                  .reduce((a, b) => a + b) /
              route!.segments.length;
      final int shadePct = (avgShade * 100).round().clamp(0, 100);
      subtitle = '$etaMin min  •  $distLabel ($shadePct% tree shade)';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFEDF0F5)),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            destinationLabel,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.titleSmall?.copyWith(
              color: const Color(0xFF0E1B2A),
              fontWeight: FontWeight.w700,
            ),
          ),
          if (subtitle != null) ...<Widget>[
            const SizedBox(height: 4),
            Text(
              subtitle,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(
                color: const Color(0xFF5E6D80),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _WeatherBanner extends StatelessWidget {
  const _WeatherBanner();

  @override
  Widget build(BuildContext context) {
    // Shown when hot-day context is applicable.
    // In the current app there is no weather API; the banner is static.
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF8E1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: <Widget>[
          const Icon(
            Icons.wb_sunny_outlined,
            color: Color(0xFFF59E0B),
            size: 18,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Hot conditions today — shade-aware routing enabled',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: const Color(0xFF92400E),
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class MapCircleButton extends StatelessWidget {
  const MapCircleButton({
    super.key,
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    this.iconColor = const Color(0xFF162133),
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;
  final Color iconColor;

  @override
  Widget build(BuildContext context) {
    return ClipOval(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
        child: Material(
          color: Colors.white.withValues(alpha: 0.84),
          child: IconButton(
            tooltip: tooltip,
            onPressed: onPressed,
            icon: Icon(icon, color: iconColor),
            style: IconButton.styleFrom(
              minimumSize: const Size(56, 56),
              shape: const CircleBorder(),
              side: BorderSide(color: Colors.white.withValues(alpha: 0.60)),
              shadowColor: Colors.black.withValues(alpha: 0.10),
              elevation: 6,
            ),
          ),
        ),
      ),
    );
  }
}

class MapToggleChip extends StatelessWidget {
  const MapToggleChip({
    super.key,
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      curve: Curves.easeOut,
      decoration: BoxDecoration(
        color: isSelected
            ? Colors.white.withValues(alpha: 0.96)
            : Colors.white.withValues(alpha: 0.78),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(
          color: isSelected
              ? const Color(0x332F6EF6)
              : Colors.white.withValues(alpha: 0.68),
        ),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 18,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(22),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(
                  icon,
                  size: 18,
                  color: isSelected
                      ? const Color(0xFF2F6EF6)
                      : const Color(0xFF54657A),
                ),
                const SizedBox(width: 8),
                Text(
                  label,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: const Color(0xFF162133),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class HintChip extends StatelessWidget {
  const HintChip({super.key, required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.78),
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: Colors.white.withValues(alpha: 0.66)),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Icon(icon, size: 18, color: const Color(0xFF617286)),
            const SizedBox(width: 8),
            Text(
              label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: const Color(0xFF617286),
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class EmergencyButton extends StatelessWidget {
  const EmergencyButton({super.key, required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: <Color>[Color(0xFFE3424B), Color(0xFFD52A37)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: const Color(0xFFE3424B).withValues(alpha: 0.26),
            blurRadius: 24,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(24),
          child: const Padding(
            padding: EdgeInsets.symmetric(horizontal: 16, vertical: 16),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(Icons.emergency_rounded, color: Colors.white),
                SizedBox(width: 8),
                Text(
                  'SOS',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.3,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class HomeScreenBody extends StatelessWidget {
  const HomeScreenBody({
    super.key,
    required this.mapController,
    required this.initialCenter,
    required this.safetyZones,
    required this.showSafetyZones,
    required this.routePolylines,
    required this.markers,
    required this.destinationLabel,
    required this.isLoadingRoute,
    required this.isLoadingLocation,
    required this.showHintChip,
    required this.showCompassReset,
    required this.actionBottomOffset,
    required this.navState,
    required this.route,
    required this.isRerouting,
    this.savedPlacesBar,
    required this.onMapReady,
    required this.onMapTap,
    required this.onPositionChanged,
    required this.onRecenter,
    required this.onSearchTap,
    required this.onClearRoute,
    required this.profileIcon,
    required this.profileIconColor,
    required this.profileTooltip,
    required this.onOpenProfile,
    required this.onToggleSafetyZones,
    required this.onResetCompass,
    required this.onReportIncident,
    required this.onTriggerSos,
    required this.onStartNavigation,
    required this.onStopNavigation,
    required this.onDismissArrival,
    required this.onCardExpansionChanged,
  });

  final MapController mapController;
  final LatLng initialCenter;
  final List<SafetyZone> safetyZones;
  final bool showSafetyZones;
  final List<Polyline> routePolylines;
  final List<Marker> markers;
  final String? destinationLabel;
  final bool isLoadingRoute;
  final bool isLoadingLocation;
  final bool showHintChip;
  final bool showCompassReset;
  final double actionBottomOffset;
  final NavigationState navState;
  final ScoredRoute? route;
  final bool isRerouting;
  final Widget? savedPlacesBar;
  final VoidCallback onMapReady;
  final ValueChanged<LatLng> onMapTap;
  final ValueChanged<MapCamera> onPositionChanged;
  final VoidCallback onRecenter;
  final VoidCallback onSearchTap;
  final VoidCallback? onClearRoute;
  final IconData profileIcon;
  final Color profileIconColor;
  final String profileTooltip;
  final VoidCallback onOpenProfile;
  final VoidCallback onToggleSafetyZones;
  final VoidCallback onResetCompass;
  final VoidCallback onReportIncident;
  final VoidCallback onTriggerSos;
  final VoidCallback onStartNavigation;
  final VoidCallback onStopNavigation;
  final VoidCallback onDismissArrival;
  final ValueChanged<bool> onCardExpansionChanged;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: <Widget>[
        WalkSafeMapView(
          mapController: mapController,
          initialCenter: initialCenter,
          initialZoom: 14.8,
          onMapReady: onMapReady,
          overlayLayers: <Widget>[
            if (showSafetyZones)
              RepaintBoundary(
                child: SafetyZoneOverlay(zones: safetyZones),
              ),
          ],
          routePolylines: routePolylines,
          markers: markers,
          onTap: onMapTap,
          onPositionChanged: onPositionChanged,
        ),
        const IgnorePointer(
          child: Align(
            alignment: Alignment.topCenter,
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: <Color>[
                    Color(0x66FFFFFF),
                    Color(0x18FFFFFF),
                    Color(0x00FFFFFF),
                  ],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
              child: SizedBox(height: 180, width: double.infinity),
            ),
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                // Top header: WalkSafe logo row (matches reference image)
                Row(
                  children: <Widget>[
                    // WalkSafe shield logo area
                    DecoratedBox(
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.90),
                        borderRadius: BorderRadius.circular(14),
                        boxShadow: <BoxShadow>[
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.08),
                            blurRadius: 12,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: <Widget>[
                            const Icon(
                              Icons.shield_rounded,
                              color: Color(0xFF1B6B3A),
                              size: 22,
                            ),
                            const SizedBox(width: 8),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Text(
                                  'WalkSafe',
                                  style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                    color: const Color(0xFF0E1B2A),
                                    fontWeight: FontWeight.w800,
                                    height: 1.1,
                                  ),
                                ),
                                Text(
                                  'Climate',
                                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                    color: const Color(0xFF1B6B3A),
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    // Search bar in middle (when route in progress)
                    if (navState != NavigationState.idle) ...<Widget>[
                      Expanded(
                        child: HomeSearchPanel(
                          destinationLabel: destinationLabel,
                          isLoadingRoute: isLoadingRoute,
                          onTap: onSearchTap,
                          onClear: onClearRoute,
                        ),
                      ),
                      const SizedBox(width: 10),
                    ] else
                      const Spacer(),
                    // Profile / avatar button
                    MapCircleButton(
                      icon: profileIcon,
                      iconColor: profileIconColor,
                      tooltip: profileTooltip,
                      onPressed: onOpenProfile,
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (savedPlacesBar != null) ...<Widget>[
                  savedPlacesBar!,
                  const SizedBox(height: 12),
                ],
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: <Widget>[
                    MapToggleChip(
                      label: 'Show Safety Zones',
                      icon: showSafetyZones
                          ? Icons.visibility_rounded
                          : Icons.visibility_off_rounded,
                      isSelected: showSafetyZones,
                      onTap: onToggleSafetyZones,
                    ),
                    if (showHintChip)
                      const HintChip(
                        icon: Icons.touch_app_rounded,
                        label: 'Tap anywhere to preview a safe route',
                      ),
                  ],
                ),
              ],
            ),
          ),
        ),
        Positioned(
          right: 16,
          bottom: actionBottomOffset,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              if (showCompassReset) ...<Widget>[
                MapCircleButton(
                  icon: Icons.explore_rounded,
                  tooltip: 'Reset compass',
                  onPressed: onResetCompass,
                ),
                const SizedBox(height: 12),
              ],
              MapCircleButton(
                icon: Icons.report_gmailerrorred_rounded,
                tooltip: 'Report incident',
                onPressed: onReportIncident,
              ),
              const SizedBox(height: 12),
              EmergencyButton(onPressed: onTriggerSos),
            ],
          ),
        ),
        Positioned(
          left: 16,
          right: 16,
          bottom: 24,
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 260),
            switchInCurve: Curves.easeOutCubic,
            switchOutCurve: Curves.easeInCubic,
            transitionBuilder: (Widget child, Animation<double> animation) {
              final Animation<Offset> offsetAnimation = Tween<Offset>(
                begin: const Offset(0, 0.12),
                end: Offset.zero,
              ).animate(animation);
              return FadeTransition(
                opacity: animation,
                child: SlideTransition(position: offsetAnimation, child: child),
              );
            },
            child: navState == NavigationState.idle
                ? WalkSafeBottomSheet(
                    key: const ValueKey<String>('idle-sheet'),
                    destinationLabel: destinationLabel,
                    route: route,
                    isLoadingRoute: isLoadingRoute,
                    onSearchTap: onSearchTap,
                    onFindSafeRoute: onStartNavigation,
                    onClearRoute: onClearRoute,
                  )
                : NavigationCard(
                    key: const ValueKey<String>('nav-card'),
                    navState: navState,
                    route: route,
                    destinationLabel: destinationLabel,
                    isLoadingRoute: isLoadingRoute,
                    isRerouting: isRerouting,
                    onStartNavigation: onStartNavigation,
                    onStopNavigation: onStopNavigation,
                    onDismissArrival: onDismissArrival,
                    onExpansionChanged: onCardExpansionChanged,
                  ),
          ),
        ),
        if (isLoadingLocation)
          const Positioned.fill(
            child: ColoredBox(
              color: Color(0x66FFFFFF),
              child: Center(
                child: CircularProgressIndicator(color: Color(0xFF2E7CF6)),
              ),
            ),
          ),
      ],
    );
  }
}

Future<void> showIncidentReportDialog({
  required BuildContext context,
  required LatLng initialLocation,
}) {
  return showGeneralDialog<void>(
    context: context,
    barrierDismissible: true,
    barrierLabel: 'Close incident report',
    barrierColor: Colors.black.withValues(alpha: 0.30),
    transitionDuration: const Duration(milliseconds: 220),
    pageBuilder:
        (
          BuildContext context,
          Animation<double> animation,
          Animation<double> secondaryAnimation,
        ) => ReportIncidentScreen(initialLocation: initialLocation),
    transitionBuilder:
        (
          BuildContext context,
          Animation<double> animation,
          Animation<double> secondaryAnimation,
          Widget child,
        ) {
          final Animation<double> curvedAnimation = CurvedAnimation(
            parent: animation,
            curve: Curves.easeOutCubic,
          );
          return FadeTransition(
            opacity: curvedAnimation,
            child: ScaleTransition(
              scale: Tween<double>(
                begin: 0.96,
                end: 1,
              ).animate(curvedAnimation),
              child: child,
            ),
          );
        },
  );
}

Future<void> showSosLocationRequiredDialog(BuildContext context) {
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (_) => AlertDialog(
      title: const Text('Location required for SOS'),
      content: const Text(
        'ResilientSteps needs your GPS location to send an accurate SOS alert.\n\n'
        'Please enable location permissions in your phone settings, then try again.\n\n'
        'If you need immediate help, call 112.',
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('OK'),
        ),
        TextButton(
          onPressed: () {
            Navigator.of(context).pop();
            Geolocator.openLocationSettings();
          },
          child: const Text('Open settings'),
        ),
      ],
    ),
  );
}

Future<void> showSosResultDialog({
  required BuildContext context,
  required bool sent,
}) {
  return showDialog<void>(
    context: context,
    builder: (BuildContext context) {
      return AlertDialog(
        title: Text(sent ? 'SOS Alert Sent' : 'SOS Alert Failed'),
        content: Text(
          sent
              ? 'Your emergency alert has been recorded. Move toward a brighter, busier area if you can.'
              : 'Could not reach the backend. Please call local emergency services directly.',
        ),
        actions: <Widget>[
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('OK'),
          ),
        ],
      );
    },
  );
}

class _NavMetricCard extends StatelessWidget {
  const _NavMetricCard({
    required this.label,
    required this.value,
    required this.sublabel,
    required this.labelColor,
    required this.backgroundColor,
  });

  final String label;
  final String value;
  final String sublabel;
  final Color labelColor;
  final Color backgroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: labelColor,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
              color: const Color(0xFF0E1B2A),
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            sublabel,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: labelColor.withValues(alpha: 0.75),
            ),
          ),
        ],
      ),
    );
  }
}

class _RouteChip extends StatelessWidget {
  const _RouteChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFF0E1B2A) : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: selected
                ? const Color(0xFF0E1B2A)
                : const Color(0xFFD0D8E4),
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            if (selected) ...<Widget>[
              const Icon(
                Icons.check_rounded,
                color: Colors.white,
                size: 14,
              ),
              const SizedBox(width: 4),
            ],
            Text(
              label,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: selected
                    ? Colors.white
                    : const Color(0xFF4E5E73),
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _GlassPanel extends StatelessWidget {
  const _GlassPanel({required this.child, required this.borderRadius});

  final Widget child;
  final double borderRadius;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 18, sigmaY: 18),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.82),
            borderRadius: BorderRadius.circular(borderRadius),
            border: Border.all(color: Colors.white.withValues(alpha: 0.70)),
            boxShadow: <BoxShadow>[
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.08),
                blurRadius: 18,
                offset: const Offset(0, 10),
              ),
            ],
          ),
          child: child,
        ),
      ),
    );
  }
}

class _NavigationMetric extends StatelessWidget {
  const _NavigationMetric({
    required this.label,
    required this.value,
    this.alignEnd = false,
  });

  final String label;
  final String value;
  final bool alignEnd;

  @override
  Widget build(BuildContext context) {
    final CrossAxisAlignment alignment = alignEnd
        ? CrossAxisAlignment.end
        : CrossAxisAlignment.start;

    return Column(
      crossAxisAlignment: alignment,
      children: <Widget>[
        Text(
          label,
          textAlign: alignEnd ? TextAlign.end : TextAlign.start,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
            color: const Color(0xFF617286),
            fontWeight: FontWeight.w700,
            letterSpacing: 0.3,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          value,
          textAlign: alignEnd ? TextAlign.end : TextAlign.start,
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            color: const Color(0xFF0C1522),
            fontWeight: FontWeight.w900,
          ),
        ),
      ],
    );
  }
}
