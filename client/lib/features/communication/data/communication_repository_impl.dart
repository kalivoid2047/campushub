import 'dart:convert';

import '../../../core/error/app_exception.dart';
import '../../../core/network/api_client.dart';
import '../../../core/storage/local_database.dart';
import '../../../core/utils/uuid.dart';
import '../domain/communication_repository.dart';

/// Announcements are network-first with entity-cache fallback (docs/09
/// section 7). sendMessage queues to the local sync queue when offline,
/// matching the backend's "messages" sync-entity handler
/// (backend app/modules/communication/sync_handler.py).
class CommunicationRepositoryImpl implements CommunicationRepository {
  CommunicationRepositoryImpl(this._api, this._db);

  final ApiClient _api;
  final LocalDatabase _db;

  @override
  Future<List<AnnouncementSummary>> listAnnouncements() async {
    try {
      final rows = await _api.getJsonList('/api/v1/announcements');
      final announcements = [
        for (final row in rows)
          AnnouncementSummary.fromJson(row as Map<String, dynamic>)
      ];
      for (final announcement in announcements) {
        await _db.upsertEntity(
          entityTable: 'announcements',
          entityId: announcement.id,
          payloadJson: jsonEncode(announcement.toJson()),
          serverVersion: 1,
        );
      }
      return announcements;
    } on NetworkUnavailableException {
      final cached = await _db.listEntities('announcements');
      return [
        for (final row in cached)
          AnnouncementSummary.fromJson(
            jsonDecode(row['payload'] as String) as Map<String, dynamic>,
          )
      ]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    }
  }

  @override
  Future<ChannelSummary> getCourseChannel(String courseId) async {
    final json = await _api.getJson('/api/v1/courses/$courseId/channel');
    return ChannelSummary.fromJson(json);
  }

  @override
  Future<ChannelSummary> getOrCreateDm(String recipientId) async {
    final json = await _api.postJson(
      '/api/v1/channels/dm',
      {'recipient_id': recipientId},
    );
    return ChannelSummary.fromJson(json);
  }

  @override
  Future<MessagePageResult> listMessages(
    String channelId, {
    String? before,
  }) async {
    final json = await _api.getJson(
      '/api/v1/channels/$channelId/messages',
      query: before == null ? null : {'before': before},
    );
    final messages = [
      for (final row in json['messages'] as List<dynamic>)
        MessageItem.fromJson(row as Map<String, dynamic>)
    ];
    return MessagePageResult(
      messages: messages,
      nextCursor: json['next_cursor'] as String?,
      hasMore: json['has_more'] as bool,
    );
  }

  @override
  Future<MessageItem> sendMessage(
    String channelId,
    String body, {
    required String currentUserId,
  }) async {
    // client_id makes a retried send idempotent server-side (docs/06 s6)
    // and, offline, doubles as the sync-queue idempotency key (docs/09 s2).
    final clientId = newUuid();
    try {
      final json = await _api.postJson('/api/v1/channels/$channelId/messages', {
        'body': body,
        'client_id': clientId,
      });
      return MessageItem.fromJson(json);
    } on NetworkUnavailableException {
      await _db.enqueue(
        clientId: clientId,
        entityTable: 'messages',
        entityId: newUuid(),
        operation: 'create',
        payloadJson: jsonEncode({'channel_id': channelId, 'body': body}),
      );
      return MessageItem(
        id: clientId,
        channelId: channelId,
        senderId: currentUserId,
        body: body,
        createdAt: DateTime.now(),
        pending: true,
      );
    }
  }
}
