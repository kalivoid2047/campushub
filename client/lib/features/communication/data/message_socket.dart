import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../../../core/network/api_client.dart';
import '../domain/communication_repository.dart';

/// Minimal transport seam so [MessageSocket] doesn't hard-depend on a real
/// network socket — tests inject a fake, production uses the real one.
abstract class SocketTransport {
  Stream<dynamic> get stream;
  Future<void> close();
}

class _WebSocketTransport implements SocketTransport {
  _WebSocketTransport(Uri uri) : _channel = WebSocketChannel.connect(uri);

  final WebSocketChannel _channel;

  @override
  Stream<dynamic> get stream => _channel.stream;

  @override
  Future<void> close() => _channel.sink.close();
}

typedef TransportFactory = SocketTransport Function(Uri uri);

/// Live message delivery over the ticket-authenticated WebSocket channel
/// (docs/06-api-design.md section 7): `POST /ws/ticket` then connect to
/// `/ws/channels/{id}?ticket=...`. The socket is delivery-only — the
/// REST send (and, later, the sync engine) remain the durable source of
/// truth; a dropped socket just means the next manual refresh catches up.
class MessageSocket {
  MessageSocket(this._api, {TransportFactory? transportFactory})
      : _transportFactory =
            transportFactory ?? ((uri) => _WebSocketTransport(uri));

  final ApiClient _api;
  final TransportFactory _transportFactory;

  SocketTransport? _transport;
  StreamSubscription<dynamic>? _subscription;
  final _controller = StreamController<MessageItem>.broadcast();

  Stream<MessageItem> get messages => _controller.stream;

  Future<void> connect(String channelId) async {
    final ticketResponse = await _api.postJson('/api/v1/ws/ticket', const {});
    final ticket = ticketResponse['ticket'] as String;
    final wsBase = _api.baseUrl.replaceFirst(RegExp('^http'), 'ws');
    final uri =
        Uri.parse('$wsBase/api/v1/ws/channels/$channelId?ticket=$ticket');

    _transport = _transportFactory(uri);
    _subscription = _transport!.stream.listen(
      (raw) {
        final data = jsonDecode(raw as String) as Map<String, dynamic>;
        if (data['type'] == 'message.created' && !_controller.isClosed) {
          _controller.add(MessageItem.fromSocketEvent(data));
        }
      },
      // A dropped connection is not fatal — the thread still works via REST;
      // we simply stop receiving live pushes until the screen reconnects.
      onError: (_) {},
    );
  }

  Future<void> dispose() async {
    await _subscription?.cancel();
    await _transport?.close();
    await _controller.close();
  }
}
