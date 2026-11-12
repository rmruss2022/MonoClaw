import WidgetKit
import SwiftUI

// MARK: - Brand

let brandPurple = Color(red: 0.659, green: 0.333, blue: 0.969)
let brandPink = Color(red: 0.925, green: 0.286, blue: 0.600)

// MARK: - Networking

func fetchJSON<T: Decodable>(_ urlString: String, as type: T.Type) async -> T? {
    guard let url = URL(string: urlString) else { return nil }
    var req = URLRequest(url: url)
    req.cachePolicy = .reloadIgnoringLocalCacheData
    req.timeoutInterval = 12
    do {
        let (data, _) = try await URLSession.shared.data(for: req)
        return try JSONDecoder().decode(T.self, from: data)
    } catch {
        return nil
    }
}

func nextRefresh(minutes: Int = 30) -> Date {
    Calendar.current.date(byAdding: .minute, value: minutes, to: Date()) ?? Date().addingTimeInterval(1800)
}

@ViewBuilder
func widgetBackground<Content: View>(_ content: Content) -> some View {
    if #available(iOS 17.0, *) {
        content.containerBackground(for: .widget) { Color(.systemBackground) }
    } else {
        content.background(Color(.systemBackground))
    }
}

// MARK: - To-do widget

struct TodoItem: Decodable { let text: String; let done: Bool }
struct TodoResp: Decodable { let todos: [TodoItem] }

struct TodoEntry: TimelineEntry { let date: Date; let todos: [TodoItem] }

struct TodoProvider: TimelineProvider {
    func placeholder(in context: Context) -> TodoEntry {
        TodoEntry(date: Date(), todos: [TodoItem(text: "Loading…", done: false)])
    }
    func getSnapshot(in context: Context, completion: @escaping (TodoEntry) -> Void) {
        completion(TodoEntry(date: Date(), todos: [TodoItem(text: "Tap to open Dash", done: false)]))
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<TodoEntry>) -> Void) {
        Task {
            let r = await fetchJSON("https://dash.bedrock.casa/api/todo", as: TodoResp.self)
            let entry = TodoEntry(date: Date(), todos: r?.todos ?? [])
            completion(Timeline(entries: [entry], policy: .after(nextRefresh())))
        }
    }
}

struct TodoWidgetView: View {
    var entry: TodoEntry
    var open: [TodoItem] { entry.todos.filter { !$0.done } }
    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack {
                Text("TO-DO").font(.system(size: 11, weight: .heavy)).tracking(1.2).foregroundColor(brandPurple)
                Spacer()
                if !entry.todos.isEmpty {
                    Text("\(entry.todos.count - open.count)/\(entry.todos.count)")
                        .font(.system(size: 11, weight: .semibold)).foregroundColor(.secondary)
                }
            }
            if open.isEmpty {
                Text(entry.todos.isEmpty ? "Nothing yet" : "All done ✓")
                    .font(.system(size: 14)).foregroundColor(.secondary)
            } else {
                ForEach(Array(open.prefix(4).enumerated()), id: \.offset) { _, t in
                    HStack(spacing: 8) {
                        Circle().strokeBorder(brandPurple.opacity(0.65), lineWidth: 2).frame(width: 13, height: 13)
                        Text(t.text).font(.system(size: 13)).lineLimit(1).foregroundColor(.primary)
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(14)
    }
}

struct DashTodoWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "DashTodo", provider: TodoProvider()) { entry in
            widgetBackground(TodoWidgetView(entry: entry))
        }
        .configurationDisplayName("To-do")
        .description("Your shared Dash to-do list.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

// MARK: - Upcoming events widget

struct EventItem: Decodable {
    let date: String?
    let time: String?
    let title: String?
    let venue: String?
    let category: String?
    let near_home: Bool?
}
struct EventResp: Decodable { let events: [EventItem] }

struct EventsEntry: TimelineEntry { let date: Date; let events: [EventItem] }

struct EventsProvider: TimelineProvider {
    func placeholder(in context: Context) -> EventsEntry {
        EventsEntry(date: Date(), events: [])
    }
    func getSnapshot(in context: Context, completion: @escaping (EventsEntry) -> Void) {
        completion(EventsEntry(date: Date(), events: []))
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<EventsEntry>) -> Void) {
        Task {
            let r = await fetchJSON("https://marquee.bedrock.casa/api/widget", as: EventResp.self)
            let entry = EventsEntry(date: Date(), events: r?.events ?? [])
            completion(Timeline(entries: [entry], policy: .after(nextRefresh(minutes: 60))))
        }
    }
}

func shortDate(_ iso: String?) -> (String, String) {
    guard let iso = iso else { return ("", "") }
    let parts = iso.split(separator: "-")
    guard parts.count == 3, let m = Int(parts[1]), let d = Int(parts[2]) else { return ("", "") }
    let mon = ["", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    return (m >= 1 && m <= 12 ? mon[m] : "", String(d))
}

struct EventsWidgetView: View {
    @Environment(\.widgetFamily) var family
    var entry: EventsEntry
    var limit: Int { family == .systemSmall ? 2 : 4 }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("WHAT'S ON").font(.system(size: 11, weight: .heavy)).tracking(1.2).foregroundColor(brandPink)
                Spacer()
                Text("NYC").font(.system(size: 11, weight: .semibold)).foregroundColor(.secondary)
            }
            if entry.events.isEmpty {
                Text("No events").font(.system(size: 14)).foregroundColor(.secondary)
            } else {
                ForEach(Array(entry.events.prefix(limit).enumerated()), id: \.offset) { _, e in
                    let dt = shortDate(e.date)
                    HStack(spacing: 9) {
                        VStack(spacing: 0) {
                            Text(dt.0).font(.system(size: 8, weight: .bold)).foregroundColor(brandPink)
                            Text(dt.1).font(.system(size: 15, weight: .bold)).foregroundColor(.primary)
                        }.frame(width: 26)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(e.title ?? "Event").font(.system(size: 13, weight: .medium)).lineLimit(1)
                            if family != .systemSmall {
                                Text([e.time, e.venue].compactMap { $0 }.joined(separator: " · "))
                                    .font(.system(size: 11)).foregroundColor(.secondary).lineLimit(1)
                            }
                        }
                        Spacer(minLength: 0)
                    }
                }
            }
            Spacer(minLength: 0)
        }
        .padding(14)
    }
}

struct DashEventsWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "DashEvents", provider: EventsProvider()) { entry in
            widgetBackground(EventsWidgetView(entry: entry))
        }
        .configurationDisplayName("Upcoming events")
        .description("The next things happening in NYC, from Marquee.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

// MARK: - Daily report widget

struct ReportData: Decodable { let date: String?; let title: String?; let text: String? }
struct ReportResp: Decodable { let report: ReportData? }

struct ReportEntry: TimelineEntry { let date: Date; let report: ReportData? }

struct ReportProvider: TimelineProvider {
    func placeholder(in context: Context) -> ReportEntry {
        ReportEntry(date: Date(), report: ReportData(date: "", title: "Daily report", text: "Loading…"))
    }
    func getSnapshot(in context: Context, completion: @escaping (ReportEntry) -> Void) {
        completion(ReportEntry(date: Date(), report: ReportData(date: "", title: "Daily report", text: "Your morning briefing.")))
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<ReportEntry>) -> Void) {
        Task {
            let r = await fetchJSON("https://dash.bedrock.casa/api/report-latest", as: ReportResp.self)
            let entry = ReportEntry(date: Date(), report: r?.report)
            completion(Timeline(entries: [entry], policy: .after(nextRefresh(minutes: 60))))
        }
    }
}

struct ReportWidgetView: View {
    @Environment(\.widgetFamily) var family
    var entry: ReportEntry
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("DAILY REPORT").font(.system(size: 11, weight: .heavy)).tracking(1.2).foregroundColor(brandPurple)
                Spacer()
                if let d = entry.report?.date, !d.isEmpty {
                    Text(d).font(.system(size: 10)).foregroundColor(.secondary).lineLimit(1)
                }
            }
            Text(entry.report?.title ?? "No report yet")
                .font(.system(size: 15, weight: .bold)).lineLimit(1).foregroundColor(.primary)
            Text(entry.report?.text ?? "Your morning briefing will appear here.")
                .font(.system(size: 12)).foregroundColor(.secondary)
                .lineLimit(family == .systemSmall ? 3 : 7)
            Spacer(minLength: 0)
        }
        .padding(14)
    }
}

struct DashReportWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "DashReport", provider: ReportProvider()) { entry in
            widgetBackground(ReportWidgetView(entry: entry))
        }
        .configurationDisplayName("Daily report")
        .description("Your latest morning briefing.")
        .supportedFamilies([.systemSmall, .systemMedium, .systemLarge])
    }
}

// MARK: - Bundle

@main
struct DashWidgetsBundle: WidgetBundle {
    var body: some Widget {
        DashTodoWidget()
        DashEventsWidget()
        DashReportWidget()
    }
}
