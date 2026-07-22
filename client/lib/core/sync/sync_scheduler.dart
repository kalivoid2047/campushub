import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

import 'sync_engine.dart';

/// Drives [SyncEngine.runSyncCycle] automatically (docs/09-offline-sync.md
/// section 4: background sync), so the manual sync button becomes a
/// convenience rather than the only way data ever moves.
///
/// Triggers:
///  - an immediate cycle on [start] (catch up on whatever queued while the
///    app was closed),
///  - a periodic cycle every [interval] as a steady heartbeat,
///  - an immediate cycle the moment connectivity transitions from
///    none → available, so a reconnect doesn't wait for the next tick.
///
/// [runCycle] and [connectivityChanges] are injected (rather than
/// constructing a SyncEngine/Connectivity internally) so tests can drive
/// this deterministically without a platform channel.
class SyncScheduler {
  SyncScheduler(
    this._runCycle, {
    this.interval = const Duration(minutes: 2),
    Stream<List<ConnectivityResult>>? connectivityChanges,
  }) : _connectivityChanges =
            connectivityChanges ?? Connectivity().onConnectivityChanged;

  final Future<SyncResult> Function() _runCycle;
  final Duration interval;
  final Stream<List<ConnectivityResult>> _connectivityChanges;

  Timer? _timer;
  StreamSubscription<List<ConnectivityResult>>? _connectivitySub;
  final _results = StreamController<SyncResult>.broadcast();
  bool _wasOffline = false;
  bool _started = false;

  Stream<SyncResult> get results => _results.stream;

  void start() {
    if (_started) return;
    _started = true;
    _timer = Timer.periodic(interval, (_) => _runSafely());
    _connectivitySub = _connectivityChanges.listen((statuses) {
      final online = statuses.any((s) => s != ConnectivityResult.none);
      if (online && _wasOffline) _runSafely();
      _wasOffline = !online;
    });
    unawaited(_runSafely());
  }

  /// Triggers an immediate cycle outside the regular cadence (e.g. a manual
  /// "Sync now" button) without disturbing the periodic timer.
  Future<void> runNow() => _runSafely();

  Future<void> _runSafely() async {
    try {
      final result = await _runCycle();
      if (!_results.isClosed) _results.add(result);
    } catch (_) {
      // Transient failures retry on the next tick or the next reconnect —
      // nothing queued locally is lost either way (docs/09 section 9).
    }
  }

  void dispose() {
    _timer?.cancel();
    _connectivitySub?.cancel();
    _results.close();
  }
}
