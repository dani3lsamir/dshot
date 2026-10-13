using System;
using System.Collections.Generic;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using Microsoft.Win32;
using Drawing = System.Drawing;
using Drawing2D = System.Drawing.Drawing2D;
using Forms = System.Windows.Forms;
using MediaColor = System.Windows.Media.Color;
using PixelFormat = System.Drawing.Imaging.PixelFormat;
using PointF = System.Drawing.PointF;
using Rectangle = System.Windows.Shapes.Rectangle;

namespace dshot;

internal sealed class OverlayWindow : Window
{
    private enum EditMode { Select, Rectangle, Arrow, Pen, Text }
    private sealed class Mark
    {
        public required EditMode Type { get; init; }
        public required MediaColor Color { get; init; }
        public Point Start { get; init; }
        public Point End { get; set; }
        public List<Point> Points { get; } = new();
        public string Text { get; set; } = "";
        public UIElement? Visual { get; set; }
    }

    private readonly Drawing.Bitmap _snapshot;
    private readonly Canvas _canvas = new() { Background = Brushes.Transparent, ClipToBounds = true };
    private readonly Border _toolbar = new();
    // Lightshot-style selection: a white edge with a dark inner line, readable on light and dark content.
    private readonly Border _selection = new()
    {
        BorderBrush = Brushes.White,
        BorderThickness = new Thickness(1),
        Child = new Border { BorderBrush = new SolidColorBrush(MediaColor.FromArgb(140, 0, 0, 0)), BorderThickness = new Thickness(1) },
        IsHitTestVisible = false,
        Visibility = Visibility.Collapsed
    };
    // Everything outside the selection is dimmed; the selected region keeps its real brightness.
    private readonly RectangleGeometry _dimArea = new();
    private readonly RectangleGeometry _dimHole = new(Rect.Empty);
    private readonly List<Mark> _marks = new();
    private readonly MediaColor[] _palette =
    {
        Colors.Red, Colors.DodgerBlue, Colors.LimeGreen, Colors.Yellow, Colors.White
    };
    private int _paletteIndex;
    private EditMode _mode = EditMode.Select;
    private Point _start;
    private Rect _selected = Rect.Empty;
    private bool _dragging;
    private Mark? _activeMark;
    private TextBox? _textEdit;
    private Point _textPosition;
    private bool _busy;

    private const double TextFontSize = 20;
    private static readonly FontFamily TextFont = new("Segoe UI"); // Same face the exported PNG uses.
    // Distance from a TextBox's origin to its first glyph (1px border + 2px caret margin), so typed text
    // sits exactly where the committed annotation is drawn.
    private static readonly Vector TextBoxInset = new(3, 1);

    // A region is ready once the first selection is accepted; annotation modes replace Select from then on.
    private bool HasSelection => _mode != EditMode.Select;

    public OverlayWindow()
    {
        Title = "dshot";
        WindowStyle = WindowStyle.None;
        ResizeMode = ResizeMode.NoResize;
        WindowState = WindowState.Maximized;
        ShowInTaskbar = false;
        Topmost = true;
        Background = Brushes.Black;
        Focusable = true;

        // Grab pixels before opening any overlay; exported files never include dshot controls.
        var screen = Forms.Screen.PrimaryScreen ?? throw new InvalidOperationException("No primary screen found.");
        var bounds = screen.Bounds;
        _snapshot = new Drawing.Bitmap(bounds.Width, bounds.Height, PixelFormat.Format32bppArgb);
        using (var graphics = Drawing.Graphics.FromImage(_snapshot))
            graphics.CopyFromScreen(bounds.Location, Drawing.Point.Empty, bounds.Size, Drawing.CopyPixelOperation.SourceCopy);

        var image = new System.Windows.Controls.Image { Source = ToBitmapSource(_snapshot), Stretch = Stretch.Fill,
            IsHitTestVisible = false };
        var dim = new System.Windows.Shapes.Path
        {
            Fill = new SolidColorBrush(MediaColor.FromArgb(110, 0, 0, 0)),
            Data = new GeometryGroup { FillRule = FillRule.EvenOdd, Children = { _dimArea, _dimHole } },
            IsHitTestVisible = false
        };
        _canvas.SizeChanged += (_, e) => _dimArea.Rect = new Rect(e.NewSize);
        var grid = new Grid();
        grid.Children.Add(image);
        grid.Children.Add(dim);
        grid.Children.Add(_canvas);
        Content = grid;

        _canvas.Children.Add(_selection);
        CreateToolbar();
        _canvas.Children.Add(_toolbar);
        _canvas.MouseLeftButtonDown += OnCanvasMouseDown;
        _canvas.MouseMove += OnCanvasMouseMove;
        _canvas.MouseLeftButtonUp += OnCanvasMouseUp;
        PreviewKeyDown += KeyPressed;
        Closed += (_, _) => _snapshot.Dispose();
        Loaded += (_, _) => Focus();
    }

    // Copies the pixels straight into a WPF bitmap (Format32bppArgb is BGRA in memory). Avoids a PNG
    // encode/decode of the whole screen, so the overlay opens faster and uses less memory.
    private static BitmapSource ToBitmapSource(Drawing.Bitmap bitmap)
    {
        var data = bitmap.LockBits(new Drawing.Rectangle(0, 0, bitmap.Width, bitmap.Height),
            ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        try
        {
            var source = BitmapSource.Create(bitmap.Width, bitmap.Height, 96, 96, PixelFormats.Bgra32, null,
                data.Scan0, data.Stride * bitmap.Height, data.Stride);
            source.Freeze();
            return source;
        }
        finally { bitmap.UnlockBits(data); }
    }

    // Icon-only toolbar, as in Lightshot. Icons are 16x16 stroke paths; tooltips name each tool.
    private static class Icons
    {
        public const string Rectangle = "M2.5,3.5 H13.5 V12.5 H2.5 Z";
        public const string Arrow = "M3,13 L13,3 M7.5,3 H13 V8.5";
        public const string Pen = "M2.5,13.5 L3.5,10 L10.5,3 A1.4,1.4 0 0 1 13,5.5 L6,12.5 Z M9,4.5 L11.5,7";
        public const string Text = "M3,3 H13 M8,3 V13.5 M6,13.5 H10";
        public const string Undo = "M5.5,3.5 L2.5,6.5 L5.5,9.5 M2.5,6.5 H9.5 A3.5,3.5 0 0 1 9.5,13.5 H6.5";
        public const string Ocr = "M2,5.5 V2 H5.5 M10.5,2 H14 V5.5 M14,10.5 V14 H10.5 M5.5,14 H2 V10.5 M5.5,5.5 H10.5 M8,5.5 V10.5";
        public const string Copy = "M6,6 H13.5 V13.5 H6 Z M3.5,10.5 H2.5 V2.5 H10.5 V3.5";
        public const string Save = "M2.5,2.5 H11 L13.5,5 V13.5 H2.5 Z M5,2.5 V6 H10 V2.5 M5,13.5 V9.5 H11 V13.5";
        public const string Close = "M4,4 L12,12 M12,4 L4,12";
    }

    private static readonly Brush ActiveToolBrush = new SolidColorBrush(MediaColor.FromRgb(74, 80, 90));
    private static readonly ControlTemplate ToolTemplate = (ControlTemplate)System.Windows.Markup.XamlReader.Parse(
        "<ControlTemplate xmlns='http://schemas.microsoft.com/winfx/2006/xaml/presentation' " +
        "xmlns:x='http://schemas.microsoft.com/winfx/2006/xaml' TargetType='Button'>" +
        "<Border x:Name='Chrome' Background='{TemplateBinding Background}' CornerRadius='5'>" +
        "<ContentPresenter HorizontalAlignment='Center' VerticalAlignment='Center'/></Border>" +
        "<ControlTemplate.Triggers><Trigger Property='IsMouseOver' Value='True'>" +
        "<Setter TargetName='Chrome' Property='Background' Value='#3A3F49'/></Trigger></ControlTemplate.Triggers>" +
        "</ControlTemplate>");

    private readonly Dictionary<EditMode, Button> _modeButtons = new();
    private readonly System.Windows.Shapes.Ellipse _colorSwatch = new()
    {
        Width = 12, Height = 12, Stroke = Brushes.White, StrokeThickness = 1.4
    };

    private void CreateToolbar()
    {
        var row = new StackPanel { Orientation = Orientation.Horizontal };
        _modeButtons[EditMode.Rectangle] = AddTool(row, ToolIcon(Icons.Rectangle), "Rectangle", () => SetMode(EditMode.Rectangle));
        _modeButtons[EditMode.Arrow] = AddTool(row, ToolIcon(Icons.Arrow), "Arrow", () => SetMode(EditMode.Arrow));
        _modeButtons[EditMode.Pen] = AddTool(row, ToolIcon(Icons.Pen), "Pen", () => SetMode(EditMode.Pen));
        _modeButtons[EditMode.Text] = AddTool(row, ToolIcon(Icons.Text), "Text", () => SetMode(EditMode.Text));
        _colorSwatch.Fill = new SolidColorBrush(_palette[_paletteIndex]);
        AddTool(row, _colorSwatch, "Color", NextColor);
        AddSeparator(row);
        AddTool(row, ToolIcon(Icons.Undo), "Undo (Ctrl + Z)", Undo);
        AddSeparator(row);
        AddTool(row, ToolIcon(Icons.Ocr), "Copy text — OCR (English/Spanish)", async () => await ExtractTextAsync());
        AddTool(row, ToolIcon(Icons.Copy), "Copy image (Ctrl + C)", () => CopyImage());
        AddTool(row, ToolIcon(Icons.Save), "Save as PNG (Ctrl + S)", SaveImage);
        AddSeparator(row);
        AddTool(row, ToolIcon(Icons.Close), "Close (Esc)", Close);

        _toolbar.Child = row;
        _toolbar.Background = new SolidColorBrush(MediaColor.FromRgb(31, 34, 42));
        _toolbar.BorderBrush = new SolidColorBrush(MediaColor.FromRgb(90, 96, 105));
        _toolbar.BorderThickness = new Thickness(1);
        _toolbar.CornerRadius = new CornerRadius(7);
        _toolbar.Padding = new Thickness(3);
        _toolbar.Effect = new System.Windows.Media.Effects.DropShadowEffect { BlurRadius = 12, ShadowDepth = 3, Opacity = 0.5 };
        _toolbar.Visibility = Visibility.Collapsed;
        _toolbar.Measure(new Size(double.PositiveInfinity, double.PositiveInfinity));
    }

    private static UIElement ToolIcon(string pathData) => new System.Windows.Shapes.Path
    {
        Data = Geometry.Parse(pathData),
        Width = 16, Height = 16,
        Stroke = Brushes.White, StrokeThickness = 1.5,
        StrokeStartLineCap = PenLineCap.Round, StrokeEndLineCap = PenLineCap.Round, StrokeLineJoin = PenLineJoin.Round
    };

    private static Button AddTool(Panel panel, UIElement icon, string tooltip, Action action)
    {
        var button = new Button
        {
            Content = icon,
            ToolTip = tooltip,
            Template = ToolTemplate,
            Width = 30, Height = 30,
            Margin = new Thickness(1, 0, 1, 0),
            Background = Brushes.Transparent,
            FocusVisualStyle = null,
            Cursor = Cursors.Hand
        };
        button.Click += (_, _) => action();
        panel.Children.Add(button);
        return button;
    }

    private static void AddSeparator(Panel panel) => panel.Children.Add(new Border
    {
        Width = 1, Height = 18, Margin = new Thickness(4, 0, 4, 0), VerticalAlignment = VerticalAlignment.Center,
        Background = new SolidColorBrush(MediaColor.FromRgb(74, 80, 90))
    });

    // Highlights the active drawing tool so it is clear what a drag on the screenshot will do.
    private void SetMode(EditMode mode)
    {
        _mode = mode;
        foreach (var (toolMode, button) in _modeButtons)
            button.Background = toolMode == mode ? ActiveToolBrush : Brushes.Transparent;
    }

    // Lightshot-style shortcuts: Esc closes, Ctrl+C copies, Ctrl+S saves, Ctrl+Z undoes.
    private void KeyPressed(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Escape)
        {
            // First Esc finishes the text being typed; the next one closes the capture.
            if (_textEdit is not null) CommitText();
            else Close();
            e.Handled = true;
            return;
        }
        if (_busy || Keyboard.Modifiers != ModifierKeys.Control || !HasSelection) return;
        switch (e.Key)
        {
            case Key.C:
                // Inside the text box, Ctrl+C with selected characters still copies those characters.
                if (_textEdit is { SelectionLength: > 0 }) return;
                CommitText();
                CopyImage();
                e.Handled = true;
                break;
            case Key.S:
                CommitText();
                SaveImage();
                e.Handled = true;
                break;
            case Key.Z:
                if (_textEdit is not null) return; // The text box has its own undo while typing.
                Undo();
                e.Handled = true;
                break;
        }
    }

    private void NextColor()
    {
        _paletteIndex = (_paletteIndex + 1) % _palette.Length;
        _colorSwatch.Fill = new SolidColorBrush(_palette[_paletteIndex]);
        if (_textEdit is not null)
        {
            var brush = new SolidColorBrush(_palette[_paletteIndex]);
            _textEdit.Foreground = brush;
            _textEdit.CaretBrush = brush;
        }
    }

    private void OnCanvasMouseDown(object sender, MouseButtonEventArgs e)
    {
        if (_busy) return;
        // Clicking anywhere outside the text being typed finishes it, as in Lightshot.
        if (_textEdit is not null) CommitText();
        var p = e.GetPosition(_canvas);
        if (_mode == EditMode.Select)
        {
            _start = p;
            _dragging = true;
            _toolbar.Visibility = Visibility.Collapsed;
            _selection.Visibility = Visibility.Visible;
            UpdateSelection(p);
            _canvas.CaptureMouse();
            return;
        }
        if (!_selected.Contains(p)) return;
        if (_mode == EditMode.Text) { BeginText(p); return; }

        _start = p;
        _dragging = true;
        _activeMark = new Mark { Type = _mode, Color = _palette[_paletteIndex], Start = p, End = p };
        if (_mode == EditMode.Pen) _activeMark.Points.Add(p);
        if (_mode == EditMode.Rectangle)
        {
            var rect = new Rectangle { Stroke = new SolidColorBrush(_activeMark.Color), StrokeThickness = 2.5,
                Fill = Brushes.Transparent, IsHitTestVisible = false };
            _activeMark.Visual = rect;
            _canvas.Children.Add(rect);
        }
        else
        {
            var polyline = new Polyline { Stroke = new SolidColorBrush(_activeMark.Color), StrokeThickness = 2.5,
                StrokeLineJoin = PenLineJoin.Round, StrokeStartLineCap = PenLineCap.Round,
                StrokeEndLineCap = PenLineCap.Round, IsHitTestVisible = false };
            polyline.Points.Add(p);
            _activeMark.Visual = polyline;
            _canvas.Children.Add(polyline);
        }
        _canvas.CaptureMouse();
    }

    private void OnCanvasMouseMove(object sender, MouseEventArgs e)
    {
        if (!_dragging) return;
        Point p = e.GetPosition(_canvas);
        if (_mode == EditMode.Select) { UpdateSelection(p); return; }
        p = ClampToSelection(p);
        if (_activeMark is null) return;
        _activeMark.End = p;
        if (_activeMark.Type == EditMode.Rectangle && _activeMark.Visual is Rectangle rectangle)
        {
            Rect r = Normalize(_start, p);
            Canvas.SetLeft(rectangle, r.X);
            Canvas.SetTop(rectangle, r.Y);
            rectangle.Width = r.Width;
            rectangle.Height = r.Height;
        }
        else if (_activeMark.Visual is Polyline polyline)
        {
            if (_activeMark.Type == EditMode.Pen)
            {
                _activeMark.Points.Add(p);
                polyline.Points.Add(p);
            }
            else
            {
                polyline.Points.Clear();
                polyline.Points.Add(_start);
                polyline.Points.Add(p);
            }
        }
    }

    private void OnCanvasMouseUp(object sender, MouseButtonEventArgs e)
    {
        if (!_dragging) return;
        _dragging = false;
        _canvas.ReleaseMouseCapture();
        if (_mode == EditMode.Select)
        {
            UpdateSelection(e.GetPosition(_canvas));
            if (_selected.Width < 6 || _selected.Height < 6)
            {
                _selection.Visibility = Visibility.Collapsed;
                _selected = Rect.Empty;
                _dimHole.Rect = Rect.Empty;
                return;
            }
            SetMode(EditMode.Rectangle); // When selected, toolbar lets user choose annotation mode.
            PlaceToolbar();
            return;
        }
        if (_activeMark is null) return;
        if (_activeMark.Type == EditMode.Pen && _activeMark.Points.Count < 2)
            _activeMark.Points.Add(_activeMark.End);
        if (_activeMark.Type == EditMode.Arrow)
        {
            var head = MakeArrowHead(_activeMark.Start, _activeMark.End, _activeMark.Color);
            if (head is not null)
            {
                _canvas.Children.Add(head);
                // Keep a dedicated container for undo alongside the line.
                _arrowheads[_activeMark] = head;
            }
        }
        _marks.Add(_activeMark);
        _activeMark = null;
    }

    private readonly Dictionary<Mark, Polygon> _arrowheads = new();

    private static Polygon? MakeArrowHead(Point a, Point b, MediaColor color)
    {
        Vector v = b - a;
        if (v.Length < 4) return null;
        v.Normalize();
        var perpendicular = new Vector(-v.Y, v.X);
        var basePoint = b - v * 12;
        return new Polygon
        {
            Points = new PointCollection { b, basePoint + perpendicular * 5, basePoint - perpendicular * 5 },
            Fill = new SolidColorBrush(color), IsHitTestVisible = false
        };
    }

    private void UpdateSelection(Point end)
    {
        _selected = Normalize(_start, end);
        Canvas.SetLeft(_selection, _selected.Left);
        Canvas.SetTop(_selection, _selected.Top);
        _selection.Width = _selected.Width;
        _selection.Height = _selected.Height;
        _dimHole.Rect = _selected;
    }

    private static Rect Normalize(Point a, Point b) => new(
        Math.Min(a.X, b.X), Math.Min(a.Y, b.Y), Math.Abs(a.X - b.X), Math.Abs(a.Y - b.Y));

    private Point ClampToSelection(Point p) => new(
        Math.Clamp(p.X, _selected.Left, _selected.Right),
        Math.Clamp(p.Y, _selected.Top, _selected.Bottom));

    private void PlaceToolbar()
    {
        _toolbar.Measure(new Size(double.PositiveInfinity, double.PositiveInfinity));
        double w = _toolbar.DesiredSize.Width;
        double h = _toolbar.DesiredSize.Height;
        Canvas.SetLeft(_toolbar, Math.Clamp(_selected.Left, 0, Math.Max(0, _canvas.ActualWidth - w)));
        double y = _selected.Bottom + 9;
        if (y + h > _canvas.ActualHeight) y = _selected.Top - h - 9;
        Canvas.SetTop(_toolbar, Math.Clamp(y, 0, Math.Max(0, _canvas.ActualHeight - h)));
        _toolbar.Visibility = Visibility.Visible;
    }

    private void BeginText(Point p)
    {
        // Lightshot-style overlay text: typed straight onto the screenshot in the current color, with no
        // background. The box grows as you type; Enter adds a line, clicking elsewhere or Esc finishes it.
        _textPosition = p;
        var brush = new SolidColorBrush(_palette[_paletteIndex]);
        _textEdit = new TextBox
        {
            FontFamily = TextFont, FontSize = TextFontSize, FontWeight = FontWeights.Bold, MinWidth = 24,
            Background = Brushes.Transparent, Foreground = brush, CaretBrush = brush,
            BorderBrush = new SolidColorBrush(MediaColor.FromArgb(150, 255, 255, 255)),
            BorderThickness = new Thickness(1), Padding = new Thickness(0),
            AcceptsReturn = true, TextWrapping = TextWrapping.NoWrap
        };
        Canvas.SetLeft(_textEdit, p.X - TextBoxInset.X);
        Canvas.SetTop(_textEdit, p.Y - TextBoxInset.Y);
        var box = _textEdit;
        // Only finish this box: when a new box takes focus, the old one's focus loss must not commit the new one.
        box.LostKeyboardFocus += (_, _) => { if (ReferenceEquals(_textEdit, box)) CommitText(); };
        _canvas.Children.Add(_textEdit);
        _textEdit.Focus();
    }

    private void CommitText()
    {
        if (_textEdit is null) return;
        var box = _textEdit;
        var value = box.Text.TrimEnd();
        _textEdit = null;
        _canvas.Children.Remove(box);
        if (value.Trim().Length == 0) return;
        var mark = new Mark { Type = EditMode.Text, Color = _palette[_paletteIndex], Start = _textPosition,
            End = _textPosition, Text = value };
        var visual = new TextBlock
        {
            Text = value, Foreground = new SolidColorBrush(mark.Color), FontFamily = TextFont, FontWeight = FontWeights.Bold,
            FontSize = TextFontSize, IsHitTestVisible = false
        };
        Canvas.SetLeft(visual, _textPosition.X);
        Canvas.SetTop(visual, _textPosition.Y);
        mark.Visual = visual;
        _canvas.Children.Add(visual);
        _marks.Add(mark);
    }

    private void Undo()
    {
        if (_marks.Count == 0) return;
        var mark = _marks[^1];
        _marks.RemoveAt(_marks.Count - 1);
        if (mark.Visual is not null) _canvas.Children.Remove(mark.Visual);
        if (_arrowheads.Remove(mark, out var head)) _canvas.Children.Remove(head);
    }

    private Drawing.Bitmap ComposeImage(bool annotations)
    {
        if (_selected.IsEmpty) throw new InvalidOperationException("Select a region first.");
        double xScale = _snapshot.Width / _canvas.ActualWidth;
        double yScale = _snapshot.Height / _canvas.ActualHeight;
        int x = Math.Clamp((int)Math.Floor(_selected.Left * xScale), 0, _snapshot.Width - 1);
        int y = Math.Clamp((int)Math.Floor(_selected.Top * yScale), 0, _snapshot.Height - 1);
        int w = Math.Clamp((int)Math.Ceiling(_selected.Width * xScale), 1, _snapshot.Width - x);
        int h = Math.Clamp((int)Math.Ceiling(_selected.Height * yScale), 1, _snapshot.Height - y);
        var output = new Drawing.Bitmap(w, h, PixelFormat.Format32bppArgb);
        using var graphics = Drawing.Graphics.FromImage(output);
        graphics.DrawImage(_snapshot, new Drawing.Rectangle(0, 0, w, h),
            new Drawing.Rectangle(x, y, w, h), Drawing.GraphicsUnit.Pixel);
        if (!annotations) return output;
        graphics.SmoothingMode = Drawing2D.SmoothingMode.AntiAlias;
        graphics.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAlias;
        foreach (var mark in _marks)
        {
            Drawing.Color c = Drawing.Color.FromArgb(mark.Color.A, mark.Color.R, mark.Color.G, mark.Color.B);
            PointF Pixel(Point p) => new((float)(p.X * xScale - x), (float)(p.Y * yScale - y));
            var start = Pixel(mark.Start);
            var end = Pixel(mark.End);
            using var pen = new Drawing.Pen(c, (float)Math.Max(1.5, 2.5 * xScale));
            pen.StartCap = Drawing2D.LineCap.Round;
            pen.EndCap = Drawing2D.LineCap.Round;
            if (mark.Type == EditMode.Rectangle)
            {
                float left = Math.Min(start.X, end.X), top = Math.Min(start.Y, end.Y);
                graphics.DrawRectangle(pen, left, top, Math.Abs(end.X - start.X), Math.Abs(end.Y - start.Y));
            }
            else if (mark.Type == EditMode.Arrow)
            {
                pen.CustomEndCap = new Drawing2D.AdjustableArrowCap(5, 5, true);
                graphics.DrawLine(pen, start, end);
            }
            else if (mark.Type == EditMode.Pen && mark.Points.Count >= 2)
                graphics.DrawLines(pen, mark.Points.Select(Pixel).ToArray());
            else if (mark.Type == EditMode.Text)
            {
                using var font = new Drawing.Font("Segoe UI", (float)(TextFontSize * yScale), Drawing.FontStyle.Bold, Drawing.GraphicsUnit.Pixel);
                using var brush = new Drawing.SolidBrush(c);
                // Typographic format drops GDI+'s extra left padding so the text lands where it was typed.
                using var format = Drawing.StringFormat.GenericTypographic;
                graphics.DrawString(mark.Text, font, brush, start, format);
            }
        }
        return output;
    }

    private void CopyImage()
    {
        try
        {
            using var bitmap = ComposeImage(true);
            System.Windows.Clipboard.SetImage(ToBitmapSource(bitmap));
            Close();
        }
        catch (Exception ex) { Warn(ex.Message); }
    }

    private async System.Threading.Tasks.Task ExtractTextAsync()
    {
        if (_busy) return;
        _busy = true;
        Cursor = Cursors.Wait;
        try
        {
            using var bitmap = ComposeImage(false);
            var result = await OcrService.ExtractAsync(bitmap);
            if (string.IsNullOrWhiteSpace(result))
            {
                Warn("No text found. Try a larger region or text with better contrast.");
                return;
            }
            System.Windows.Clipboard.SetText(result);
            Close();
        }
        catch (Exception ex) { Warn("Text recognition failed: " + ex.Message); }
        finally { _busy = false; Cursor = Cursors.Arrow; }
    }

    private void SaveImage()
    {
        var dialog = new SaveFileDialog { Filter = "PNG image|*.png", DefaultExt = ".png",
            AddExtension = true, FileName = $"dshot_{DateTime.Now:yyyyMMdd_HHmmss}.png" };
        if (dialog.ShowDialog(this) != true) return;
        try
        {
            using var bitmap = ComposeImage(true);
            bitmap.Save(dialog.FileName, ImageFormat.Png);
            Close();
        }
        catch (Exception ex) { Warn("Could not save: " + ex.Message); }
    }

    private void Warn(string message) => MessageBox.Show(this, message, "dshot",
        MessageBoxButton.OK, MessageBoxImage.Warning);
}
