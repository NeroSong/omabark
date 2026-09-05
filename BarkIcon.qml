import QtQuick

// A small monochrome mark inspired by Bark's opposing speaker shapes.
// Native geometry follows the bar foreground without a colored app tile.
Canvas {
    id: root
    property color foreground: "white"
    onForegroundChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        ctx.scale(width / 24, height / 24)
        ctx.fillStyle = foreground
        ctx.beginPath()
        ctx.moveTo(2, 5)
        ctx.lineTo(8, 8)
        ctx.lineTo(8, 10)
        ctx.lineTo(16, 10)
        ctx.lineTo(16, 8)
        ctx.lineTo(22, 5)
        ctx.lineTo(22, 19)
        ctx.lineTo(16, 16)
        ctx.lineTo(16, 14)
        ctx.lineTo(8, 14)
        ctx.lineTo(8, 16)
        ctx.lineTo(2, 19)
        ctx.closePath()
        ctx.fill()
    }
}
