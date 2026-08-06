import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart' as lk;

/// Live call UI (docs/10-virtual-classroom.md): connects directly to the
/// LiveKit room using the token minted by `POST /sessions/{id}/join`
/// (backend `VirtualClassroomService._media_join_info`). CampusHub's own
/// backend does not relay media or signaling — this widget talks to LiveKit
/// directly, which is the standard LiveKit client integration pattern.
class CallScreen extends StatefulWidget {
  const CallScreen({
    super.key,
    required this.signalingUrl,
    required this.sfuToken,
    required this.sessionTitle,
    required this.onLeave,
    required this.onStartRecording,
    required this.onStopRecording,
  });

  final String signalingUrl;
  final String sfuToken;
  final String sessionTitle;

  /// Called once, before popping, to record the leave server-side
  /// (closes the attendance window — FR-VC-5/FR-ATT-1).
  final Future<void> Function() onLeave;

  /// Server-side recording control (Epic E5, manual lecturer-triggered).
  /// Rejected with a 403 by the backend for non-lecturers — this widget
  /// doesn't gate the button locally, matching how Start/End session
  /// controls already trust the backend's RBAC rather than duplicating it.
  final Future<void> Function() onStartRecording;
  final Future<void> Function() onStopRecording;

  @override
  State<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends State<CallScreen> {
  final _room = lk.Room();
  lk.EventsListener<lk.RoomEvent>? _listener;
  bool _connecting = true;
  bool _leaving = false;
  bool _micEnabled = true;
  bool _cameraEnabled = true;
  bool _screenShareEnabled = false;
  bool _togglingScreenShare = false;
  bool _recording = false;
  bool _togglingRecording = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _connect();
  }

  Future<void> _connect() async {
    try {
      await _room.connect(widget.signalingUrl, widget.sfuToken);
      await _room.localParticipant?.setMicrophoneEnabled(true);
      await _room.localParticipant?.setCameraEnabled(true);
      _listener = _room.createListener();
      // Any room/participant/track change re-renders the tile grid — simpler
      // and safe (idempotent setState) rather than tracking each event kind.
      _listener!.listen((_) {
        if (mounted) setState(() {});
      });
      if (mounted) setState(() => _connecting = false);
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = '$error';
          _connecting = false;
        });
      }
    }
  }

  Future<void> _leave() async {
    if (_leaving) return;
    setState(() => _leaving = true);
    await _listener?.dispose();
    await _room.disconnect();
    try {
      await widget.onLeave();
    } catch (_) {
      // The room connection is already torn down; a failed leave-record
      // call is not worth blocking the user from exiting the call UI.
    }
    if (mounted) Navigator.of(context).pop();
  }

  @override
  void dispose() {
    _listener?.dispose();
    _room.dispose();
    super.dispose();
  }

  Future<void> _toggleMic() async {
    final next = !_micEnabled;
    await _room.localParticipant?.setMicrophoneEnabled(next);
    if (mounted) setState(() => _micEnabled = next);
  }

  Future<void> _toggleCamera() async {
    final next = !_cameraEnabled;
    await _room.localParticipant?.setCameraEnabled(next);
    if (mounted) setState(() => _cameraEnabled = next);
  }

  /// Publishes/unpublishes a screenShareVideo track (docs/10-virtual-classroom.md
  /// Epic E5 screen sharing). The join token's VideoGrants already permit
  /// publishing any track source, so no backend change is needed — this is
  /// purely a client-side capability. Wrapped in try/catch (unlike mic/camera)
  /// because the browser/OS source picker is commonly cancelled by the user,
  /// which is routine here, not exceptional.
  Future<void> _toggleScreenShare() async {
    if (_togglingScreenShare) return;
    final next = !_screenShareEnabled;
    setState(() => _togglingScreenShare = true);
    try {
      await _room.localParticipant?.setScreenShareEnabled(next);
      if (mounted) setState(() => _screenShareEnabled = next);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Screen share unavailable: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _togglingScreenShare = false);
    }
  }

  /// Starts/stops server-side recording. Unlike mic/camera/screen-share this
  /// is not a local media action — it round-trips to the backend, which
  /// mints a LiveKit Egress job (Epic E5). A failure (not a lecturer, or
  /// recording not configured on this server) is routine enough to surface
  /// as a SnackBar rather than tearing down the call.
  Future<void> _toggleRecording() async {
    if (_togglingRecording) return;
    final next = !_recording;
    setState(() => _togglingRecording = true);
    try {
      if (next) {
        await widget.onStartRecording();
      } else {
        await widget.onStopRecording();
      }
      if (mounted) setState(() => _recording = next);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Recording: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _togglingRecording = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (!didPop) await _leave();
      },
      child: Scaffold(
        backgroundColor: Colors.black,
        appBar: AppBar(
          title: Text(widget.sessionTitle),
          backgroundColor: Colors.black87,
          foregroundColor: Colors.white,
          actions: [
            if (_recording)
              const Padding(
                padding: EdgeInsets.only(right: 16),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.fiber_manual_record,
                        color: Colors.red, size: 14),
                    SizedBox(width: 4),
                    Text('REC', style: TextStyle(color: Colors.red)),
                  ],
                ),
              ),
          ],
        ),
        body: _connecting
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(_error!,
                          style: const TextStyle(color: Colors.white)),
                    ),
                  )
                : _buildGrid(),
        bottomNavigationBar: _connecting || _error != null
            ? null
            : Container(
                color: Colors.black87,
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    IconButton(
                      tooltip: _micEnabled ? 'Mute' : 'Unmute',
                      icon: Icon(
                        _micEnabled ? Icons.mic : Icons.mic_off,
                        color: Colors.white,
                      ),
                      onPressed: _toggleMic,
                    ),
                    const SizedBox(width: 16),
                    IconButton(
                      tooltip: _cameraEnabled ? 'Stop camera' : 'Start camera',
                      icon: Icon(
                        _cameraEnabled ? Icons.videocam : Icons.videocam_off,
                        color: Colors.white,
                      ),
                      onPressed: _toggleCamera,
                    ),
                    const SizedBox(width: 16),
                    IconButton(
                      tooltip: _screenShareEnabled
                          ? 'Stop screen share'
                          : 'Share screen',
                      icon: _togglingScreenShare
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white),
                            )
                          : Icon(
                              _screenShareEnabled
                                  ? Icons.stop_screen_share
                                  : Icons.screen_share_outlined,
                              color: _screenShareEnabled
                                  ? Theme.of(context).colorScheme.primary
                                  : Colors.white,
                            ),
                      onPressed:
                          _togglingScreenShare ? null : _toggleScreenShare,
                    ),
                    const SizedBox(width: 16),
                    IconButton(
                      tooltip:
                          _recording ? 'Stop recording' : 'Start recording',
                      icon: _togglingRecording
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white),
                            )
                          : Icon(
                              _recording
                                  ? Icons.stop_circle_outlined
                                  : Icons.fiber_manual_record,
                              color: _recording ? Colors.red : Colors.white,
                            ),
                      onPressed: _togglingRecording ? null : _toggleRecording,
                    ),
                    const SizedBox(width: 16),
                    IconButton(
                      tooltip: 'Leave',
                      icon: _leaving
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(Icons.call_end, color: Colors.red),
                      onPressed: _leaving ? null : _leave,
                    ),
                  ],
                ),
              ),
      ),
    );
  }

  Widget _buildGrid() {
    final tiles = <Widget>[
      _ParticipantTile(participant: _room.localParticipant, label: 'You'),
      for (final participant in _room.remoteParticipants.values)
        _ParticipantTile(participant: participant, label: participant.identity),
    ];
    return GridView.count(
      crossAxisCount: tiles.length <= 2 ? 1 : 2,
      children: tiles,
    );
  }
}

class _ParticipantTile extends StatelessWidget {
  const _ParticipantTile({required this.participant, required this.label});

  final lk.Participant? participant;
  final String label;

  @override
  Widget build(BuildContext context) {
    final publications = participant?.videoTrackPublications ?? const [];
    // A participant may publish both a camera and a screen-share track at
    // once; the screen share is the one worth showing.
    lk.TrackPublication? preferred;
    for (final publication in publications) {
      if (publication.source == lk.TrackSource.screenShareVideo) {
        preferred = publication;
        break;
      }
      preferred ??= publication;
    }
    final track = preferred?.track;

    return Container(
      margin: const EdgeInsets.all(4),
      color: Colors.grey.shade900,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (track is lk.VideoTrack)
            lk.VideoTrackRenderer(track)
          else
            const Center(
                child: Icon(Icons.person, size: 48, color: Colors.white54)),
          Positioned(
            left: 8,
            bottom: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              color: Colors.black45,
              child: Text(label,
                  style: const TextStyle(color: Colors.white, fontSize: 12)),
            ),
          ),
        ],
      ),
    );
  }
}
