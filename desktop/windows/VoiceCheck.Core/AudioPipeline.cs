using System.Buffers.Binary;

namespace VoiceCheck.Core;

// Device-rate mono audio; the existing backend resamples to 16 kHz with ffmpeg.
public sealed class AudioPipeline
{
    private readonly int rate, channels, bits, bytesPerFrame, meterFrames;
    private readonly bool floatingPoint;
    private readonly List<short> samples = [];
    private double energy;
    private int count;
    public event Action<double[]>? Levels;
    public event Action<byte[]>? Window;

    public AudioPipeline(int sampleRate, int channels, int bits, bool floatingPoint)
    {
        if (sampleRate < 8000 || sampleRate > 192000 || channels < 1 || channels > 32 ||
            (floatingPoint ? bits != 32 : bits is not (16 or 24 or 32)))
            throw new ArgumentException("Unsupported loopback audio format. Use a standard PCM or float output device.");
        (rate, this.channels, this.bits, this.floatingPoint) = (sampleRate, channels, bits, floatingPoint);
        bytesPerFrame = channels * bits / 8;
        meterFrames = sampleRate / 20;
    }

    public void Reset() { samples.Clear(); energy = 0; count = 0; }

    public void Feed(ReadOnlySpan<byte> bytes)
    {
        if (bytes.Length % bytesPerFrame != 0) throw new ArgumentException("Incomplete audio frame.");
        List<double> levels = [];
        for (var frame = 0; frame < bytes.Length; frame += bytesPerFrame)
        {
            double mono = 0;
            for (var channel = 0; channel < channels; channel++)
            {
                var input = bytes.Slice(frame + channel * bits / 8, bits / 8);
                double value;
                if (floatingPoint) value = BitConverter.Int32BitsToSingle(BinaryPrimitives.ReadInt32LittleEndian(input));
                else if (bits == 16) value = BinaryPrimitives.ReadInt16LittleEndian(input) / 32768.0;
                else if (bits == 24)
                {
                    var pcm = input[0] | input[1] << 8 | input[2] << 16;
                    value = (pcm << 8 >> 8) / 8388608.0;
                }
                else value = BinaryPrimitives.ReadInt32LittleEndian(input) / 2147483648.0;
                mono += double.IsFinite(value) ? value : 0;
            }
            mono /= channels;
            energy += mono * mono;
            if (++count == meterFrames)
            {
                var db = 20 * Math.Log10(Math.Max(Math.Sqrt(energy / count), .000001));
                levels.Add(Math.Clamp((db + 60) / 48, 0, 1));
                count = 0; energy = 0;
            }
            samples.Add((short)(Math.Clamp(mono, -1, 1) * 32767));
            if (samples.Count == rate * 5)
            {
                var wav = EncodeWav(samples, rate);
                samples.Clear();
                Window?.Invoke(wav);
            }
        }
        if (levels.Count > 0) Levels?.Invoke(levels.ToArray());
    }

    public static byte[] EncodeWav(IReadOnlyList<short> pcm, int rate)
    {
        using var stream = new MemoryStream();
        using var writer = new BinaryWriter(stream);
        writer.Write("RIFF"u8); writer.Write(36 + pcm.Count * 2); writer.Write("WAVEfmt "u8);
        writer.Write(16); writer.Write((short)1); writer.Write((short)1);
        writer.Write(rate); writer.Write(rate * 2); writer.Write((short)2); writer.Write((short)16);
        writer.Write("data"u8); writer.Write(pcm.Count * 2);
        foreach (var sample in pcm) writer.Write(sample);
        return stream.ToArray();
    }
}
