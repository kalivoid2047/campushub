// dart:io (Directory/Platform) must never be referenced on a code path that
// can execute on web — even inside a `kIsWeb ? … : …` branch, since Dart
// still needs to compile/evaluate that branch, and dart:io's web shim
// throws UnsupportedError at runtime for most members (docs/08 section 5:
// web has reduced offline capability, but "reduced" must not mean "crashes
// before runApp()"). Everything dart:io-shaped is confined to
// _openNativeDownloadsDirectory below, called only when !kIsWeb.
import 'dart:io' show Directory;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart' as sqflite;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:sqflite_common_ffi_web/sqflite_ffi_web.dart';

import 'app/providers.dart';
import 'app/router.dart';
import 'app/theme/theme.dart';
import 'core/storage/local_database.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  LocalDatabase? db;
  Directory? downloadsDirectory;

  if (kIsWeb) {
    // IndexedDB-file-backed persistence can stall waiting on a browser
    // storage-permission API that never resolves outside a full user
    // gesture context; :memory: sidesteps that entirely (no persistence
    // is an already-documented web limitation, docs/09 section 7). The
    // timeout is a hard backstop: if it fires, [localDatabaseProvider] is
    // left un-overridden below, so only screens that actually touch local
    // storage fail (with Riverpod's clear "provider not overridden"
    // error) instead of the whole app hanging on a blank page.
    try {
      db = await LocalDatabase.open(
        inMemoryDatabasePath,
        factory: databaseFactoryFfiWebNoWebWorker,
      ).timeout(const Duration(seconds: 8));
    } catch (error) {
      // ignore: avoid_print
      print('Web local database unavailable ($error) — continuing without '
          'it; offline-cache/download features will error if used.');
    }
    // Downloaded-file storage isn't implemented on web yet (docs/09
    // section 5) regardless of whether the line above succeeded.
  } else {
    sqfliteFfiInit();
    sqflite.databaseFactory = databaseFactoryFfi;
    final dbDir = await sqflite.getDatabasesPath();
    db = await LocalDatabase.open(
      p.join(dbDir, 'campushub.db'),
      factory: databaseFactoryFfi,
    );
    downloadsDirectory = Directory(
      p.join((await getApplicationSupportDirectory()).path, 'downloads'),
    );
  }

  runApp(
    ProviderScope(
      overrides: [
        if (db != null) localDatabaseProvider.overrideWithValue(db),
        if (downloadsDirectory != null)
          downloadsDirectoryProvider.overrideWithValue(downloadsDirectory),
      ],
      child: const CampusHubApp(),
    ),
  );
}

class CampusHubApp extends StatelessWidget {
  const CampusHubApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'CampusHub',
      theme: CampusHubTheme.light(),
      darkTheme: CampusHubTheme.dark(),
      routerConfig: appRouter,
    );
  }
}
