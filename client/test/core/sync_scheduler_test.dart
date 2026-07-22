import 'dart:async';

import 'package:campushub/core/sync/sync_engine.dart';
import 'package:campushub/core/sync/sync_scheduler.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_test/flutter_test.dart';

SyncResult _fakeResult({bool offline = false}) => SyncResult(
      pushed: 0,
      conflicts: 0,
      rejected: 0,
      pulled: 0,
      offline: offline,
    );

void main() {
  test('start() runs an immediate cycle and then ticks on the interval',
      () async {
    var calls = 0;
    final connectivity = StreamController<List<ConnectivityResult>>.broadcast();
    final scheduler = SyncScheduler(
      () async {
        calls++;
        return _fakeResult();
      },
      interval: const Duration(milliseconds: 20),
      connectivityChanges: connectivity.stream,
    );

    scheduler.start();
    await Future.delayed(const Duration(milliseconds: 5));
    expect(calls, 1); // immediate cycle on start

    await Future.delayed(const Duration(milliseconds: 60));
    expect(calls, greaterThanOrEqualTo(3)); // periodic ticks followed

    scheduler.dispose();
    await connectivity.close();
  });

  test('reconnect after an offline stretch triggers an immediate cycle',
      () async {
    var calls = 0;
    final connectivity = StreamController<List<ConnectivityResult>>.broadcast();
    final scheduler = SyncScheduler(
      () async {
        calls++;
        return _fakeResult();
      },
      interval: const Duration(minutes: 10), // won't fire during the test
      connectivityChanges: connectivity.stream,
    );

    scheduler.start();
    await Future.delayed(const Duration(milliseconds: 5));
    expect(calls, 1); // the initial start() cycle

    connectivity.add([ConnectivityResult.none]);
    await Future.delayed(const Duration(milliseconds: 5));
    expect(calls, 1); // going offline does not trigger a cycle

    connectivity.add([ConnectivityResult.wifi]);
    await Future.delayed(const Duration(milliseconds: 5));
    expect(calls, 2); // reconnect triggers exactly one more cycle

    scheduler.dispose();
    await connectivity.close();
  });

  test('results stream reports each cycle outcome', () async {
    final connectivity = StreamController<List<ConnectivityResult>>.broadcast();
    final scheduler = SyncScheduler(
      () async => _fakeResult(offline: true),
      interval: const Duration(minutes: 10),
      connectivityChanges: connectivity.stream,
    );

    final received = <SyncResult>[];
    final sub = scheduler.results.listen(received.add);

    scheduler.start();
    await Future.delayed(const Duration(milliseconds: 5));

    expect(received, hasLength(1));
    expect(received.single.offline, isTrue);

    await sub.cancel();
    scheduler.dispose();
    await connectivity.close();
  });

  test('a throwing cycle does not crash the scheduler or stop future ticks',
      () async {
    var calls = 0;
    final connectivity = StreamController<List<ConnectivityResult>>.broadcast();
    final scheduler = SyncScheduler(
      () async {
        calls++;
        if (calls == 1) throw Exception('boom');
        return _fakeResult();
      },
      interval: const Duration(milliseconds: 15),
      connectivityChanges: connectivity.stream,
    );

    scheduler.start();
    await Future.delayed(const Duration(milliseconds: 40));
    expect(calls, greaterThanOrEqualTo(2)); // survived the first failure

    scheduler.dispose();
    await connectivity.close();
  });

  test('runNow() fires an out-of-band cycle', () async {
    var calls = 0;
    final connectivity = StreamController<List<ConnectivityResult>>.broadcast();
    final scheduler = SyncScheduler(
      () async {
        calls++;
        return _fakeResult();
      },
      interval: const Duration(minutes: 10),
      connectivityChanges: connectivity.stream,
    );
    scheduler.start();
    await Future.delayed(const Duration(milliseconds: 5));
    expect(calls, 1);

    await scheduler.runNow();
    expect(calls, 2);

    scheduler.dispose();
    await connectivity.close();
  });
}
