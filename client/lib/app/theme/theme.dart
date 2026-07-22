import 'package:flutter/material.dart';

/// Material 3 theme per docs/07-ui-ux.md §5.
/// Seed color is CampusHub's default brand seed; per-tenant override is a
/// post-MVP admin setting (see docs/07-ui-ux.md §5, §8).
class CampusHubTheme {
  static const Color _seed = Color(0xFF1E5AA8);

  static ThemeData light() => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
            seedColor: _seed, brightness: Brightness.light),
      );

  static ThemeData dark() => ThemeData(
        useMaterial3: true,
        colorScheme:
            ColorScheme.fromSeed(seedColor: _seed, brightness: Brightness.dark),
      );
}
