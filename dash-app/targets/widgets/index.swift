import WidgetKit
import SwiftUI
import AppIntents

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

struct TodoItem: Decodable {
    let id: String?; let text: String; let done: Bool
    // Explicit memberwise init: a Decodable struct does not get one for free
    // once it is also constructed by hand, and PendingToggles rebuilds rows.
    init(id: String?, text: String, done: Bool) { self.id = id; self.text = text; self.done = done }
}
struct TodoResp: Decodable { let todos: [TodoItem] }

// Interactive: check a task off straight from the widget (iOS 17+). Toggles via
// the shared API, then reloads the widget so the row updates in place.
@available(iOS 16.0, *)
struct ToggleTodoIntent: AppIntent {
    static var title: LocalizedStringResource = "Toggle a to-do"
    @Parameter(title: "Task ID") var id: String

    init() {}
    init(id: String) { self.id = id }

    func perform() async throws -> some IntentResult {
        // Record the intended state *before* the round trip. The reload below
        // refetches the list, and between the write landing and the read showing
        // it the row would otherwise redraw unticked — the checkbox springing
        // back under the finger that just tapped it.
        PendingToggles.set(id: id, done: true)
        WidgetCenter.shared.reloadAllTimelines()

        if let url = URL(string: "https://dash.bedrock.casa/api/todo/toggle") {
            var req = URLRequest(url: url)
            req.httpMethod = "POST"
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try? JSONSerialization.data(withJSONObject: ["id": id])
            req.timeoutInterval = 12
            _ = try? await URLSession.shared.data(for: req)
        }
        WidgetCenter.shared.reloadAllTimelines()
        return .result()
    }
}

// Toggles this widget has made but not yet seen confirmed by the API.
//
// Deliberately the extension's own UserDefaults and not an App Group: no group
// is configured for this app, adding one is a provisioning change, and nothing
// outside the widget needs to read this.
//
// Entries are reconciled, never just accumulated — once the API reports a task
// at the state recorded here the note is dropped. Left to grow, a stale local
// override would eventually mask a genuine change made on another device.
enum PendingToggles {
    private static let key = "dash.todo.pending"

    static func all() -> [String: Bool] {
        (UserDefaults.standard.dictionary(forKey: key) as? [String: Bool]) ?? [:]
    }
    static func set(id: String, done: Bool) {
        var m = all(); m[id] = done
        UserDefaults.standard.set(m, forKey: key)
    }
    static func reconcile(against todos: [TodoItem]) {
        var m = all()
        guard !m.isEmpty else { return }
        // uniquingKeysWith, not uniqueKeysWithValues: the latter traps on a
        // duplicate key, and a repeated id from the API would crash the widget
        // rather than merely confuse it.
        let byID = Dictionary(todos.compactMap { t in t.id.map { ($0, t.done) } },
                              uniquingKeysWith: { first, _ in first })
        for (id, want) in m where byID[id] == want || byID[id] == nil {
            m.removeValue(forKey: id)
        }
        UserDefaults.standard.set(m, forKey: key)
    }
    static func apply(to todos: [TodoItem]) -> [TodoItem] {
        let m = all()
        guard !m.isEmpty else { return todos }
        return todos.map { t in
            guard let id = t.id, let want = m[id], want != t.done else { return t }
            return TodoItem(id: t.id, text: t.text, done: want)
        }
    }
}

struct TodoEntry: TimelineEntry { let date: Date; let todos: [TodoItem] }

struct TodoProvider: TimelineProvider {
    func placeholder(in context: Context) -> TodoEntry {
        TodoEntry(date: Date(), todos: [TodoItem(id: nil, text: "Loading…", done: false)])
    }
    func getSnapshot(in context: Context, completion: @escaping (TodoEntry) -> Void) {
        completion(TodoEntry(date: Date(), todos: [TodoItem(id: nil, text: "Tap to open Dash", done: false)]))
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<TodoEntry>) -> Void) {
        Task {
            let r = await fetchJSON("https://dash.bedrock.casa/api/todo", as: TodoResp.self)
            let fetched = r?.todos ?? []
            // Drop any local override the server has now caught up with, then
            // show the rest on top of the fetched list.
            PendingToggles.reconcile(against: fetched)
            let entry = TodoEntry(date: Date(), todos: PendingToggles.apply(to: fetched))
            // Ten rather than thirty: a to-do list changes through the day, and
            // nothing else in this app asks the widget to reload. iOS still
            // decides — the policy is a request against a daily budget — but
            // asking for ten lands far closer than asking for thirty.
            completion(Timeline(entries: [entry], policy: .after(nextRefresh(minutes: 10))))
        }
    }
}

struct TodoWidgetView: View {
    var entry: TodoEntry
    var open: [TodoItem] { entry.todos.filter { !$0.done } }

    @ViewBuilder
    func checkbox(for t: TodoItem) -> some View {
        let ring = Circle().strokeBorder(brandPurple.opacity(0.65), lineWidth: 2).frame(width: 15, height: 15)
        if #available(iOS 17.0, *), let id = t.id {
            Button(intent: ToggleTodoIntent(id: id)) { ring }
                .buttonStyle(.plain)
        } else {
            ring
        }
    }

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
                        checkbox(for: t)
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
