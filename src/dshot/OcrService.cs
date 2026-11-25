using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Globalization;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using Windows.Globalization;
using Windows.Graphics.Imaging;
using Windows.Media.Ocr;
using Windows.Storage.Streams;

namespace dshot;

internal static class OcrService
{
    private const string SpanishMarks = "áéíóúüñÁÉÍÓÚÜÑ¿¡";

    public static async Task<string> ExtractAsync(Bitmap original)
    {
        var languages = OcrEngine.AvailableRecognizerLanguages.ToArray();
        if (languages.Length == 0)
            throw new InvalidOperationException("No OCR language packs are installed. Add English and/or Spanish in Settings > Time & language > Language & region.");

        // One recognizer per language is enough; prefer the system's own variant (e.g. es-MX over es-ES).
        string uiTag = CultureInfo.CurrentUICulture.Name;
        var preferred = new List<Language>(2);
        AddBest(preferred, languages, "es", uiTag);
        AddBest(preferred, languages, "en", uiTag);
        if (preferred.Count == 0)
            throw new InvalidOperationException("No English or Spanish OCR recognizer was found. Install the matching Windows language packs.");

        // Scaling and the pixel copy are pure CPU work; keep them off the UI thread.
        using var softwareBitmap = await Task.Run(() =>
        {
            using var prepared = PrepareForOcr(original);
            return ToSoftwareBitmap(prepared);
        });

        string best = string.Empty;
        double bestScore = double.NegativeInfinity;
        foreach (var language in preferred)
        {
            var engine = OcrEngine.TryCreateFromLanguage(language);
            if (engine is null) continue;
            var result = await engine.RecognizeAsync(softwareBitmap);
            string candidate = string.Join(Environment.NewLine,
                result.Lines.Select(line => line.Text.Trim()).Where(line => line.Length > 0));
            if (candidate.Length == 0) continue;

            bool isSpanish = language.LanguageTag.StartsWith("es", StringComparison.OrdinalIgnoreCase);
            double score = candidate.Count(char.IsLetter)
                + candidate.Count(char.IsDigit) * 0.7
                + (isSpanish ? candidate.Count(c => SpanishMarks.Contains(c)) * 1.5 : 0)
                - candidate.Count(c => c == '�') * 5;
            if (score > bestScore) { best = candidate; bestScore = score; }
        }
        return best;
    }

    private static void AddBest(List<Language> target, Language[] all, string prefix, string uiTag)
    {
        var pick = all
            .Where(l => l.LanguageTag.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            .OrderByDescending(l => l.LanguageTag.Equals(uiTag, StringComparison.OrdinalIgnoreCase))
            .FirstOrDefault();
        if (pick is not null) target.Add(pick);
    }

    // Upscaling small captures (as the Linux/Tesseract path does) noticeably improves recognition of
    // small UI text; a white border gives the engine quiet margins. Both are capped by the OCR size limit.
    private static Bitmap PrepareForOcr(Bitmap original)
    {
        double scale = original.Height < 100 ? 3d : original.Height < 400 ? 2d : 1d;
        int pad = scale > 1d ? 12 : 0;
        int max = (int)OcrEngine.MaxImageDimension;
        if (max > 0)
        {
            double limit = (max - pad * 2) / (double)Math.Max(1, Math.Max(original.Width, original.Height));
            if (limit > 0) scale = Math.Min(scale, limit);
        }

        int w = Math.Max(1, (int)Math.Round(original.Width * scale));
        int h = Math.Max(1, (int)Math.Round(original.Height * scale));
        var bitmap = new Bitmap(w + pad * 2, h + pad * 2, PixelFormat.Format32bppRgb);
        using var graphics = Graphics.FromImage(bitmap);
        if (pad > 0) graphics.Clear(Color.White);
        graphics.InterpolationMode = InterpolationMode.HighQualityBicubic;
        graphics.PixelOffsetMode = PixelOffsetMode.HighQuality;
        graphics.DrawImage(original, new Rectangle(pad, pad, w, h));
        return bitmap;
    }

    private static SoftwareBitmap ToSoftwareBitmap(Bitmap input)
    {
        var rect = new Rectangle(0, 0, input.Width, input.Height);
        BitmapData data = input.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppRgb);
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
