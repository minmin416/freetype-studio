import AppKit
let data = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
let board = NSPasteboard.general
board.clearContents()
let item = NSPasteboardItem()
item.setData(data, forType: NSPasteboard.PasteboardType("public.svg-image"))
item.setString(String(data: data, encoding: .utf8)!, forType: .string)
board.writeObjects([item])
