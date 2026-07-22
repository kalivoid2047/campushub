import 'dart:async';
import 'dart:convert';

import 'package:campushub/core/network/api_client.dart';
import 'package:campushub/features/communication/data/message_socket.dart';
import 'package:campushub/features/communication/domain/communication_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// A fake transport whose incoming stream we control directly from the test
/// — no real socket, no platform channel.
class _FakeTransport implements SocketTransport {
  final _incoming = StreamController<dynamic>.broadcast();
  Uri? capturedUri;
  var closed = false;

  void emit(Map<String, dynamic> event) => _incoming.add(jsonEncode(event));

  @override
  Stream<dynamic> get stream => _incoming.stream;

  @override
  Future<void> close() async {
    closed = true;
    await _incoming.close();
  }
}

void main() {
  test('connect fetches a ticket and builds the channel URL from it', () async {
    Uri? capturedTicketRequest;
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        capturedTicketRequest = request.url;
        expect(request.url.path, '/api/v1/ws/ticket');
        return http.Response(
          jsonEncode({'ticket': 'single-use-ticket', 'expires_in': 60}),
          200,
        );
      }),
    );

    late Uri connectedUri;
    final transport = _FakeTransport();
    final socket = MessageSocket(
      api,
      transportFactory: (uri) {
        connectedUri = uri;
        transport.capturedUri = uri;
        return transport;
      },
    );

    await socket.connect('ch-1');

    expect(capturedTicketRequest?.path, '/api/v1/ws/ticket');
    expect(connectedUri.scheme, 'ws');
    expect(connectedUri.path, '/api/v1/ws/channels/ch-1');
    expect(connectedUri.queryParameters['ticket'], 'single-use-ticket');

    await socket.dispose();
  });

  test('emits MessageItem only for message.created events', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        return http.Response(
            jsonEncode({'ticket': 't', 'expires_in': 60}), 200);
      }),
    );
    final transport = _FakeTransport();
    final socket = MessageSocket(api, transportFactory: (_) => transport);
    await socket.connect('ch-1');

    final received = <MessageItem>[];
    final sub = socket.messages.listen(received.add);

    // Irrelevant event type is ignored.
    transport.emit({'type': 'typing', 'channel_id': 'ch-1'});
    await Future.delayed(Duration.zero);
    expect(received, isEmpty);

    transport.emit({
      'type': 'message.created',
      'id': 'm-1',
      'channel_id': 'ch-1',
      'sender_id': 'u-2',
      'body': 'live hello',
      'created_at': '2026-07-16T00:00:00Z',
    });
    await Future.delayed(Duration.zero);

    expect(received, hasLength(1));
    expect(received.single.body, 'live hello');
    expect(received.single.senderId, 'u-2');

    await sub.cancel();
    await socket.dispose();
  });

  test('dispose closes the transport and the message stream', () async {
    final api = ApiClient(
      'http://api.test',
      httpClient: MockClient((request) async {
        return http.Response(
            jsonEncode({'ticket': 't', 'expires_in': 60}), 200);
      }),
    );
    final transport = _FakeTransport();
    final socket = MessageSocket(api, transportFactory: (_) => transport);
    await socket.connect('ch-1');

    await socket.dispose();
    expect(transport.closed, isTrue);
  });
}
