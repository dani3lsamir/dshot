using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading.Tasks;
using Windows.Graphics.Imaging;
using Windows.Media.Ocr;
using Windows.Storage.Streams;

namespace dshot;

internal static class OcrService
{
    public static async Task<string> ExtractAsync(Bitmap original)
    {
        var languages = OcrEngine.AvailableRecognizerLanguages.ToArray();
        if (languages.Length == 0)
            throw new InvalidOperationException("No OCR language packs are installed. Add English and/or Spanish in Settings > Time & language > Language & region.");

        var preferred = languages
            .Where(lang => lang.LanguageTag.StartsWith("es", StringComparison.OrdinalIgnoreCase) ||
                           lang.LanguageTag.StartsWith("en", StringComparison.OrdinalIgnoreCase))
            .OrderBy(lang => lang.LanguageTag.StartsWith("es", StringComparison.OrdinalIgnoreCase) ? 0 : 1)
            .ToArray();
        if (preferred.Length == 0)
            throw new InvalidOperationException("No English or Spanish OCR recognizer was found. Install the matching Windows language packs.");

        using var prepared = FitToOcrLimits(original);
        using var softwareBitmap = ToSoftwareBitmap(prepared);
        string best = string.Empty;
        double bestScore = -1;
        foreach (var language in preferred.Take(4))
        {
            var engine = OcrEngine.TryCreateFromLanguage(language);
            if (engine is null) continue;
            var result = await engine.RecognizeAsync(softwareBitmap);
            string candidate = string.Join(Environment.NewLine, result.Lines.Select(line => line.Text.Trim()).Where(line => line.Length > 0));
            double score = candidate.Count(char.IsLetter) + candidate.Count(char.IsDigit) * 0.7 - candidate.Count(c => c == '\uFFFD') * 5;
            if (score > bestScore) { best = candidate; bestScore = score; }
        }
        return best;
    }

    private static Bitmap FitToOcrLimits(Bitmap original)
    {
        int max = (int)OcrEngine.MaxImageDimension;
        double scale = max > 0 ? Math.Min(1d, max / (double)Math.Max(original.Width, original.Height)) : 1d;
        int w = Math.Max(1, (int)Math.Round(original.Width * scale));
        int h = Math.Max(1, (int)Math.Round(original.Height * scale));
        var bitmap = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        using var graphics = Graphics.FromImage(bitmap);
        graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
        graphics.DrawImage(original, new Rectangle(0, 0, w, h));
        return bitmap;
    }

    private static SoftwareBitmap ToSoftwareBitmap(Bitmap input)
    {
        var rect = new Rectangle(0, 0, input.Width, input.Height);
        BitmapData data = input.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        try
        {
            int rowBytes = input.Width * 4;
            var bytes = new byte[rowBytes * input.Height];
            for (int y = 0; y < input.Height; y++)
            {
                IntPtr rowPtr = IntPtr.Add(data.Scan0, y * data.Stride);
                Marshal.Copy(rowPtr, bytes, y * rowBytes, rowBytes);
            }
            using var writer = new DataWriter();
            writer.WriteBytes(bytes);
            var buffer = writer.DetachBuffer();
            return SoftwareBitmap.CreateCopyFromBuffer(buffer, BitmapPixelFormat.Bgra8,
                input.Width, input.Height, BitmapAlphaMode.Ignore);
        }
        finally { input.UnlockBits(data); }
    }
}
