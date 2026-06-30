const TARGET_SAMPLE_RATE = 16000;

function writeWavHeader(pcmData: Int16Array, sampleRate: number): ArrayBuffer {
  const numSamples = pcmData.length;
  const buffer = new ArrayBuffer(44 + numSamples * 2);
  const view = new DataView(buffer);

  const writeString = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeString(0, "RIFF");
  view.setUint32(4, 36 + numSamples * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, "data");
  view.setUint32(40, numSamples * 2, true);

  const samples = new Int16Array(buffer, 44);
  for (let i = 0; i < numSamples; i++) {
    const s = Math.max(-1, Math.min(1, pcmData[i] as unknown as number));
    samples[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  return buffer;
}

export async function audioBlobToWav(blob: Blob): Promise<Blob> {
  const arrayBuffer = await blob.arrayBuffer();

  const audioCtx = new AudioContext();
  if (audioCtx.state === "suspended") {
    await audioCtx.resume();
  }
  const decoded = await audioCtx.decodeAudioData(arrayBuffer);
  await audioCtx.close();

  const numFrames = Math.ceil(decoded.duration * TARGET_SAMPLE_RATE);
  const offlineCtx = new OfflineAudioContext(1, numFrames, TARGET_SAMPLE_RATE);

  const source = offlineCtx.createBufferSource();
  source.buffer = decoded;

  if (decoded.numberOfChannels > 1) {
    const merger = offlineCtx.createChannelMerger(1);
    source.connect(merger);
    merger.connect(offlineCtx.destination);
  } else {
    source.connect(offlineCtx.destination);
  }

  source.start(0);
  const resampled = await offlineCtx.startRendering();

  const float32 = resampled.getChannelData(0);

  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  const wavBuffer = writeWavHeader(int16, TARGET_SAMPLE_RATE);
  return new Blob([wavBuffer], { type: "audio/wav" });
}
