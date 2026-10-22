import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/widgets/navigation_card.dart';

void main() {
  testWidgets('idle sheet asks "are you at X?" and handles Yes/No', (
    WidgetTester tester,
  ) async {
    bool confirmed = false;
    bool changed = false;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          backgroundColor: Colors.grey,
          body: Align(
            alignment: Alignment.bottomCenter,
            child: WalkSafeBottomSheet(
              destinationLabel: null,
              route: null,
              isLoadingRoute: false,
              onSearchTap: () {},
              onClearRoute: null,
              originLabel: 'Spicer Adventist University',
              originLoading: false,
              originNeedsConfirm: true,
              onOriginConfirm: () => confirmed = true,
              onChangeOrigin: () => changed = true,
            ),
          ),
        ),
      ),
    );

    expect(
      find.text('Are you at Spicer Adventist University?'),
      findsOneWidget,
    );

    await tester.tap(find.text('Yes'));
    await tester.pump();
    expect(confirmed, isTrue);
    expect(changed, isFalse);

    await tester.tap(find.text('No'));
    await tester.pump();
    expect(changed, isTrue);
  });

  testWidgets('idle sheet shows locating state while reverse geocoding', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          backgroundColor: Colors.grey,
          body: Align(
            alignment: Alignment.bottomCenter,
            child: WalkSafeBottomSheet(
              destinationLabel: null,
              route: null,
              isLoadingRoute: false,
              onSearchTap: () {},
              onClearRoute: null,
              originLabel: null,
              originLoading: true,
              originNeedsConfirm: true,
              onOriginConfirm: () {},
              onChangeOrigin: () {},
            ),
          ),
        ),
      ),
    );

    expect(find.text('Finding your location…'), findsOneWidget);
    expect(find.text('Yes'), findsNothing);
    expect(find.text('No'), findsNothing);
  });

  testWidgets('idle sheet shows confirmed origin with change affordance', (
    WidgetTester tester,
  ) async {
    bool changed = false;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          backgroundColor: Colors.grey,
          body: Align(
            alignment: Alignment.bottomCenter,
            child: WalkSafeBottomSheet(
              destinationLabel: null,
              route: null,
              isLoadingRoute: false,
              onSearchTap: () {},
              onClearRoute: null,
              originLabel: 'Breman Chowk',
              originLoading: false,
              originNeedsConfirm: false,
              onOriginConfirm: () {},
              onChangeOrigin: () => changed = true,
            ),
          ),
        ),
      ),
    );

    expect(find.text('From: Breman Chowk'), findsOneWidget);
    await tester.tap(find.text('Change'));
    await tester.pump();
    expect(changed, isTrue);
  });

  testWidgets('idle sheet hides origin row entirely without origin data', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          backgroundColor: Colors.grey,
          body: Align(
            alignment: Alignment.bottomCenter,
            child: WalkSafeBottomSheet(
              destinationLabel: null,
              route: null,
              isLoadingRoute: false,
              onSearchTap: () {},
              onClearRoute: null,
              originLabel: null,
              originLoading: false,
              originNeedsConfirm: false,
              onOriginConfirm: () {},
              onChangeOrigin: () {},
            ),
          ),
        ),
      ),
    );

    expect(find.text('Starting point'), findsNothing);
    expect(find.text('Where do you want to walk?'), findsOneWidget);
  });
}
