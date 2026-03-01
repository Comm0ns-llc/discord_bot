#include <ncurses.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cctype>
#include <clocale>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <ctime>
#include <cwchar>
#include <iomanip>
#include <map>
#include <numeric>
#include <optional>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <sys/wait.h>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {

enum class Category {
    Info,
    Insight,
    Vibe,
    Ops,
    Misc
};

enum class SortKey {
    Cp,
    Ts,
    Vp,
    Streak,
    Info,
    Insight,
    Vibe,
    Ops
};

enum class ChannelActivityRange {
    All,
    Month,
    Week
};

struct Member {
    std::string name;
    int cp;
    int ts;
    int streak;
    int info;
    int insight;
    int vibe;
    int ops;
    int misc;
    bool online;
    std::vector<std::string> titles;
    int votes_participated;
};

struct Channel {
    std::string name;
    int messages_total;
    int messages_month;
    int messages_week;
    std::string champion;
    int active_users;
    double weight;
};

struct Vote {
    std::string id;
    std::string title;
    std::string type;
    int yes_vp;
    int no_vp;
    int voters;
    int total_eligible;
    int days_left;
};

struct Issue {
    int id;
    std::string title;
    std::string label;
    std::string priority;
    std::string status;
    std::string assignee;
};

struct FeedItem {
    std::string type;
    std::string user;
    std::string message;
};

struct MessageSample {
    std::string channel;
    std::string text;
};

struct RuleResult {
    Category category;
    double confidence;
    int stage;
};

struct Sprint {
    std::string name;
    std::string start_date;
    std::string end_date;
    std::vector<int> issue_ids;
    int bonus_cp;
};

constexpr int kMinHeight = 28;
constexpr int kMinWidth = 104;
constexpr int kHistoryWidth = 26;

int clampi(int v, int lo, int hi) {
    return std::max(lo, std::min(v, hi));
}

std::string to_lower(std::string s) {
    for (char& ch : s) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return s;
}

bool contains_url(const std::string& text) {
    return text.find("http://") != std::string::npos || text.find("https://") != std::string::npos;
}

std::string strip_non_basic(const std::string& text) {
    std::string out;
    out.reserve(text.size());
    for (unsigned char ch : text) {
        if (std::isalnum(ch) || std::isspace(ch) || std::ispunct(ch)) {
            out.push_back(static_cast<char>(ch));
        }
    }
    return out;
}

int visible_char_count(const std::string& text) {
    int count = 0;
    for (unsigned char ch : text) {
        if (!std::isspace(ch)) {
            ++count;
        }
    }
    return count;
}

const std::unordered_set<std::string> kOpsChannels = {
    "#ops",
    "#governance",
    "#announcements",
    "#sprint"
};

RuleResult rule_based_classify(const MessageSample& msg) {
    const std::string normalized = to_lower(msg.text);
    const std::string stripped = strip_non_basic(normalized);

    if (contains_url(normalized)) {
        return {Category::Info, 0.70, 1};
    }
    if (kOpsChannels.find(to_lower(msg.channel)) != kOpsChannels.end()) {
        return {Category::Ops, 0.60, 1};
    }
    if (visible_char_count(stripped) < 5) {
        return {Category::Vibe, 0.80, 1};
    }
    if (normalized.size() > 200) {
        return {Category::Insight, 0.40, 1};
    }
    return {Category::Misc, 0.00, 2};
}

int base_cp(Category c) {
    switch (c) {
        case Category::Info: return 5;
        case Category::Insight: return 4;
        case Category::Vibe: return 3;
        case Category::Ops: return 4;
        case Category::Misc: return 1;
    }
    return 1;
}

const std::map<std::string, double> kChannelWeights = {
    {"#dev", 1.2},
    {"#agri", 1.2},
    {"#book-commons", 1.2},
    {"#learning", 1.2},
    {"#article-share", 1.2},
    {"#general", 1.0},
    {"#intro", 1.0},
    {"#game", 0.8},
    {"#music", 0.8},
    {"#random", 0.8}
};

double channel_weight(const std::string& name) {
    auto it = kChannelWeights.find(to_lower(name));
    if (it == kChannelWeights.end()) {
        return 1.0;
    }
    return it->second;
}

int streak_bonus(int streak_days) {
    if (streak_days >= 30) {
        return 15;
    }
    if (streak_days >= 7) {
        return 5;
    }
    if (streak_days >= 3) {
        return 2;
    }
    return 0;
}

int calc_vp(int cumulative_effective_cp) {
    const int vp = static_cast<int>(std::floor(std::log2(static_cast<double>(cumulative_effective_cp) + 1.0))) + 1;
    return clampi(vp, 1, 6);
}

int calc_effective_vp(const Member& m) {
    const int vp = calc_vp(m.cp);
    return std::max(1, static_cast<int>(std::floor(vp * (static_cast<double>(m.ts) / 100.0))));
}

double calc_effective_cp(Category c, const std::string& channel, int ts) {
    const double cp = static_cast<double>(base_cp(c));
    const double weighted = cp * channel_weight(channel);
    return weighted * (static_cast<double>(ts) / 100.0);
}

std::string category_name(Category c) {
    switch (c) {
        case Category::Info: return "INFO";
        case Category::Insight: return "INSIGHT";
        case Category::Vibe: return "VIBE";
        case Category::Ops: return "OPS";
        case Category::Misc: return "MISC";
    }
    return "MISC";
}

std::string bar(double value, double max_value, int width, char fill = '#', char empty = '-') {
    if (width <= 0) {
        return "";
    }
    const double ratio = (max_value <= 0.0) ? 0.0 : std::clamp(value / max_value, 0.0, 1.0);
    const int filled = static_cast<int>(std::round(ratio * static_cast<double>(width)));
    return std::string(filled, fill) + std::string(width - filled, empty);
}

std::string now_hms() {
    auto t = std::time(nullptr);
    std::tm tmv{};
#if defined(_WIN32)
    localtime_s(&tmv, &t);
#else
    localtime_r(&t, &tmv);
#endif
    std::ostringstream oss;
    oss << std::put_time(&tmv, "%H:%M:%S");
    return oss.str();
}

std::string format_double(double value, int precision = 1) {
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(precision) << value;
    return oss.str();
}

std::string sort_name(SortKey key) {
    switch (key) {
        case SortKey::Cp: return "CP";
        case SortKey::Ts: return "TS";
        case SortKey::Vp: return "VP";
        case SortKey::Streak: return "STREAK";
        case SortKey::Info: return "INFO";
        case SortKey::Insight: return "INSIGHT";
        case SortKey::Vibe: return "VIBE";
        case SortKey::Ops: return "OPS";
    }
    return "CP";
}

int color_for_priority(const std::string& pri) {
    if (pri == "high" || pri == "critical") return 5;
    if (pri == "medium") return 4;
    if (pri == "low") return 7;
    return 1;
}

int color_for_status(const std::string& status) {
    if (status == "review") return 2;
    if (status == "in-progress") return 4;
    if (status == "open") return 7;
    if (status == "closed") return 3;
    return 1;
}

int color_for_feed(const std::string& type) {
    if (type == "THNX") return 6;
    if (type == "INFO") return 2;
    if (type == "INSI") return 9;
    if (type == "VOTE") return 9;
    if (type == "ISSU") return 5;
    if (type == "OPS") return 4;
    if (type == "STRK") return 4;
    if (type == "ACHV") return 4;
    return 1;
}

void draw_box(int y, int x, int h, int w, const std::string& title, int color_pair) {
    if (h < 3 || w < 4) {
        return;
    }
    attron(COLOR_PAIR(color_pair));
    mvhline(y, x + 1, ACS_HLINE, w - 2);
    mvhline(y + h - 1, x + 1, ACS_HLINE, w - 2);
    mvvline(y + 1, x, ACS_VLINE, h - 2);
    mvvline(y + 1, x + w - 1, ACS_VLINE, h - 2);
    mvaddch(y, x, ACS_ULCORNER);
    mvaddch(y, x + w - 1, ACS_URCORNER);
    mvaddch(y + h - 1, x, ACS_LLCORNER);
    mvaddch(y + h - 1, x + w - 1, ACS_LRCORNER);

    if (!title.empty() && w > 8) {
        std::string t = " " + title + " ";
        mvaddnstr(y, x + 2, t.c_str(), w - 4);
    }
    attroff(COLOR_PAIR(color_pair));
}

void put_line(int y, int x, int w, const std::string& text, int color_pair = 1, bool bold = false) {
    if (w <= 0) {
        return;
    }
    attr_t attr = COLOR_PAIR(color_pair);
    if (bold) {
        attr |= A_BOLD;
    }
    attron(attr);
    mvaddnstr(y, x, text.c_str(), w);
    attroff(attr);
}

std::string fit(const std::string& s, int w) {
    if (w <= 0) return "";
    if (static_cast<int>(s.size()) <= w) {
        return s;
    }
    if (w <= 3) {
        return s.substr(0, w);
    }
    return s.substr(0, w - 3) + "...";
}

int display_width_utf8(const std::string& text) {
    if (text.empty()) {
        return 0;
    }
    std::mbstate_t state{};
    const char* ptr = text.data();
    size_t len = text.size();
    int width = 0;

    while (len > 0) {
        wchar_t wc = 0;
        const size_t consumed = std::mbrtowc(&wc, ptr, len, &state);
        if (consumed == static_cast<size_t>(-1) || consumed == static_cast<size_t>(-2)) {
            // Treat invalid bytes as width 1 to keep table layout stable.
            std::memset(&state, 0, sizeof(state));
            ++width;
            ++ptr;
            --len;
            continue;
        }
        if (consumed == 0) {
            break;
        }
        int wcw = wcwidth(wc);
        if (wcw < 0) {
            wcw = 1;
        }
        width += wcw;
        ptr += consumed;
        len -= consumed;
    }
    return width;
}

std::string truncate_utf8_by_width(const std::string& text, int max_width) {
    if (max_width <= 0 || text.empty()) {
        return "";
    }

    std::mbstate_t state{};
    const char* ptr = text.data();
    size_t len = text.size();
    int width = 0;
    std::string out;

    while (len > 0) {
        wchar_t wc = 0;
        const size_t consumed = std::mbrtowc(&wc, ptr, len, &state);
        if (consumed == static_cast<size_t>(-1) || consumed == static_cast<size_t>(-2)) {
            std::memset(&state, 0, sizeof(state));
            if (width + 1 > max_width) {
                break;
            }
            out.push_back(*ptr);
            ++ptr;
            --len;
            ++width;
            continue;
        }
        if (consumed == 0) {
            break;
        }
        int wcw = wcwidth(wc);
        if (wcw < 0) {
            wcw = 1;
        }
        if (width + wcw > max_width) {
            break;
        }
        out.append(ptr, consumed);
        ptr += consumed;
        len -= consumed;
        width += wcw;
    }

    return out;
}

std::string pad_right_display(const std::string& text, int width) {
    const std::string clipped = truncate_utf8_by_width(text, width);
    const int used = display_width_utf8(clipped);
    return clipped + std::string(std::max(0, width - used), ' ');
}

std::string pad_left_display(const std::string& text, int width) {
    const std::string clipped = truncate_utf8_by_width(text, width);
    const int used = display_width_utf8(clipped);
    return std::string(std::max(0, width - used), ' ') + clipped;
}

std::string shell_quote(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    out.push_back('\'');
    for (char ch : value) {
        if (ch == '\'') {
            out += "'\"'\"'";
        } else {
            out.push_back(ch);
        }
    }
    out.push_back('\'');
    return out;
}

struct ShellResult {
    int exit_code = -1;
    std::vector<std::string> lines;
    std::string output;
};

ShellResult run_shell(const std::string& command) {
    ShellResult result;
    FILE* pipe = popen(command.c_str(), "r");
    if (!pipe) {
        result.output = "failed to spawn shell";
        return result;
    }

    std::array<char, 4096> buffer{};
    while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe) != nullptr) {
        result.output.append(buffer.data());
    }

    int status = pclose(pipe);
    if (status == -1) {
        result.exit_code = -1;
    } else if (WIFEXITED(status)) {
        result.exit_code = WEXITSTATUS(status);
    } else {
        result.exit_code = -1;
    }

    std::stringstream ss(result.output);
    std::string line;
    while (std::getline(ss, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (!line.empty()) {
            result.lines.push_back(line);
        }
    }
    return result;
}

std::string unescape_tsv_field(const std::string& value) {
    std::string out;
    out.reserve(value.size());
    for (size_t i = 0; i < value.size(); ++i) {
        if (value[i] == '\\' && i + 1 < value.size()) {
            ++i;
            switch (value[i]) {
                case 'n': out.push_back(' '); break;
                case 'r': out.push_back(' '); break;
                case 't': out.push_back(' '); break;
                case '\\': out.push_back('\\'); break;
                default:
                    out.push_back(value[i]);
                    break;
            }
        } else {
            out.push_back(value[i]);
        }
    }
    return out;
}

std::vector<std::string> split_tsv_line(const std::string& line) {
    std::vector<std::string> cols;
    std::string cur;
    for (char ch : line) {
        if (ch == '\t') {
            cols.push_back(unescape_tsv_field(cur));
            cur.clear();
        } else {
            cur.push_back(ch);
        }
    }
    cols.push_back(unescape_tsv_field(cur));
    return cols;
}

int to_int(const std::string& value, int fallback = 0) {
    try {
        return std::stoi(value);
    } catch (...) {
        return fallback;
    }
}

long long to_ll(const std::string& value, long long fallback = 0) {
    try {
        return std::stoll(value);
    } catch (...) {
        return fallback;
    }
}

double to_double(const std::string& value, double fallback = 0.0) {
    try {
        return std::stod(value);
    } catch (...) {
        return fallback;
    }
}

int days_from_civil(int year, unsigned month, unsigned day) {
    year -= month <= 2;
    const int era = (year >= 0 ? year : year - 399) / 400;
    const unsigned yoe = static_cast<unsigned>(year - era * 400);
    const unsigned doy = (153 * (month + (month > 2 ? -3 : 9)) + 2) / 5 + day - 1;
    const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + static_cast<int>(doe) - 719468;
}

std::tuple<int, unsigned, unsigned> civil_from_days(int z) {
    z += 719468;
    const int era = (z >= 0 ? z : z - 146096) / 146097;
    const unsigned doe = static_cast<unsigned>(z - era * 146097);
    const unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    int year = static_cast<int>(yoe) + era * 400;
    const unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    const unsigned mp = (5 * doy + 2) / 153;
    const unsigned day = doy - (153 * mp + 2) / 5 + 1;
    const unsigned month = mp + (mp < 10 ? 3 : static_cast<unsigned>(-9));
    year += month <= 2;
    return {year, month, day};
}

std::optional<int> parse_day_serial(const std::string& value) {
    if (value.size() < 10) {
        return std::nullopt;
    }
    const int year = to_int(value.substr(0, 4), -1);
    const int month = to_int(value.substr(5, 2), -1);
    const int day = to_int(value.substr(8, 2), -1);
    if (year <= 0 || month <= 0 || month > 12 || day <= 0 || day > 31) {
        return std::nullopt;
    }
    return days_from_civil(year, static_cast<unsigned>(month), static_cast<unsigned>(day));
}

int today_day_serial() {
    const std::time_t now = std::time(nullptr);
    std::tm tmv{};
#if defined(_WIN32)
    localtime_s(&tmv, &now);
#else
    localtime_r(&now, &tmv);
#endif
    return days_from_civil(tmv.tm_year + 1900, static_cast<unsigned>(tmv.tm_mon + 1), static_cast<unsigned>(tmv.tm_mday));
}

std::string iso_date_from_serial(int serial_day) {
    int year = 0;
    unsigned month = 0;
    unsigned day = 0;
    std::tie(year, month, day) = civil_from_days(serial_day);
    std::ostringstream oss;
    oss << std::setw(4) << std::setfill('0') << year
        << "-" << std::setw(2) << std::setfill('0') << month
        << "-" << std::setw(2) << std::setfill('0') << day;
    return oss.str();
}

std::string normalize_channel_label(const std::string& name, long long channel_id) {
    std::string label = name;
    if (label.empty()) {
        label = "channel-" + std::to_string(channel_id);
    }
    if (!label.empty() && label.front() != '#') {
        label = "#" + label;
    }
    return label;
}

class DashboardApp {
public:
    struct TabHit {
        int x0;
        int x1;
        int page;
    };

    struct MemberRowHit {
        int y;
        int x0;
        int x1;
        int row_index;
    };

    struct ChannelRangeHit {
        int y;
        int x0;
        int x1;
        ChannelActivityRange range;
    };

    DashboardApp() : rng_(std::random_device{}()) {
        init_empty_state();
        // Mock seed is intentionally disabled.
        // init_mock_data();
        // init_mock_histories();
        refresh_from_db(false);
    }

    void run() {
        setlocale(LC_ALL, "");
        initscr();
        cbreak();
        noecho();
        keypad(stdscr, TRUE);
        nodelay(stdscr, TRUE);
        curs_set(0);
        mousemask(ALL_MOUSE_EVENTS, nullptr);
        mouseinterval(0);

        if (has_colors()) {
            start_color();
            use_default_colors();
            if (COLORS >= 256) {
                // Muted btop-like palette: cool accents with low-contrast base colors.
                init_pair(1, 252, -1);  // primary text
                init_pair(2, 110, -1);  // cyan accent
                init_pair(3, 108, -1);  // green accent
                init_pair(4, 179, -1);  // amber accent
                init_pair(5, 174, -1);  // soft red
                init_pair(6, 146, -1);  // soft magenta
                init_pair(7, 244, -1);  // dim text
                init_pair(8, 252, 24);  // selection / active tab
                init_pair(9, 109, -1);  // blue accent
            } else {
                init_pair(1, COLOR_WHITE, -1);
                init_pair(2, COLOR_CYAN, -1);
                init_pair(3, COLOR_GREEN, -1);
                init_pair(4, COLOR_YELLOW, -1);
                init_pair(5, COLOR_RED, -1);
                init_pair(6, COLOR_MAGENTA, -1);
                init_pair(7, COLOR_WHITE, -1);
                init_pair(8, COLOR_WHITE, COLOR_BLUE);
                init_pair(9, COLOR_BLUE, -1);
            }
        }

        auto last_tick = std::chrono::steady_clock::now();
        bool running = true;

        while (running) {
            const auto now = std::chrono::steady_clock::now();
            if (now - last_tick >= std::chrono::seconds(1)) {
                tick();
                last_tick = now;
            }

            draw();

            int ch = getch();
            if (ch != ERR) {
                handle_key(ch, running);
            }

            napms(30);
        }

        endwin();
    }

private:
    struct QueryResult {
        bool ok = false;
        std::vector<std::vector<std::string>> rows;
        std::string error;
    };

    std::vector<Member> members_;
    std::vector<Channel> channels_;
    std::vector<Vote> votes_;
    std::vector<Issue> issues_;
    std::vector<FeedItem> feed_;
    std::vector<MessageSample> samples_;
    Sprint sprint_;

    std::vector<int> total_hist_;
    std::vector<int> info_hist_;
    std::vector<int> insight_hist_;
    std::vector<int> vibe_hist_;
    std::vector<int> ops_hist_;

    int page_ = 1;
    int selected_member_row_ = 0;
    SortKey sort_key_ = SortKey::Cp;
    ChannelActivityRange channel_activity_range_ = ChannelActivityRange::All;
    bool using_mock_data_ = false;
    bool db_ready_ = false;
    bool members_table_available_ = false;
    bool votes_table_available_ = false;
    bool issues_table_available_ = false;
    std::string data_status_ = "MOCK";
    std::string last_refresh_hms_ = "-";
    std::string last_error_;
    std::unordered_map<long long, std::string> user_name_by_id_;
    std::unordered_map<long long, std::string> channel_name_by_id_;
    int db_refresh_interval_sec_ = 30;
    std::chrono::steady_clock::time_point last_db_refresh_ = std::chrono::steady_clock::now();
    std::mt19937 rng_;
    std::vector<TabHit> tab_hits_;
    std::vector<MemberRowHit> member_row_hits_;
    std::vector<ChannelRangeHit> channel_range_hits_;

    QueryResult query_supabase(
        const std::string& endpoint,
        const std::vector<std::string>& query_params,
        const std::string& jq_program
    ) const {
        QueryResult out;
        std::string script = "set -o pipefail; "
                             "if [ -z \"$SUPABASE_URL\" ] || [ -z \"$SUPABASE_KEY\" ]; then "
                             "echo \"SUPABASE_URL/SUPABASE_KEY missing\"; exit 64; fi; "
                             "curl -sS --fail --get \"$SUPABASE_URL/rest/v1/" + endpoint + "\" "
                             "-H \"apikey: $SUPABASE_KEY\" "
                             "-H \"Authorization: Bearer $SUPABASE_KEY\" "
                             "2>/dev/null ";
        for (const auto& param : query_params) {
            script += "--data-urlencode " + shell_quote(param) + " ";
        }
        script += "| jq -r " + shell_quote(jq_program);

        const ShellResult shell = run_shell("bash -lc " + shell_quote(script));
        if (shell.exit_code != 0) {
            out.error = shell.output.empty() ? "query failed" : shell.output;
            return out;
        }

        out.ok = true;
        out.rows.reserve(shell.lines.size());
        for (const auto& line : shell.lines) {
            out.rows.push_back(split_tsv_line(line));
        }
        return out;
    }

    void init_empty_state() {
        members_.clear();
        channels_.clear();
        votes_.clear();
        issues_.clear();
        feed_.clear();
        samples_.clear();
        total_hist_.assign(kHistoryWidth, 0);
        info_hist_.assign(kHistoryWidth, 0);
        insight_hist_.assign(kHistoryWidth, 0);
        vibe_hist_.assign(kHistoryWidth, 0);
        ops_hist_.assign(kHistoryWidth, 0);
        feed_.push_back({"INFO", "system", "Waiting for Supabase data..."});
        samples_.push_back({"#system", "Supabase data not loaded yet."});
        const int today_serial = today_day_serial();
        sprint_ = {"Current Sprint", iso_date_from_serial(today_serial), iso_date_from_serial(today_serial + 13), {}, 20};
    }

    // Legacy mock dataset (kept for reference, currently disabled).
    void init_mock_data() {
        members_ = {
            {"Tate", 2847, 100, 34, 312, 287, 198, 156, 42, true, {"Tech-Lord", "Contributor"}, 14},
            {"Haru", 1923, 95, 21, 198, 234, 267, 89, 31, true, {"Polity-Lord", "Citizen"}, 12},
            {"Mina", 1456, 100, 15, 245, 156, 312, 67, 28, true, {"Sun", "Informant"}, 10},
            {"Ken", 1102, 88, 8, 89, 112, 356, 45, 67, false, {"Meme-Lord"}, 7},
            {"Aoi", 876, 100, 12, 187, 198, 134, 78, 19, true, {"Lore-Lord", "Thinker"}, 8},
            {"Riku", 654, 92, 5, 98, 134, 156, 145, 23, false, {"Backstage"}, 9},
            {"Yuu", 423, 100, 3, 56, 78, 178, 34, 31, true, {"Sprout"}, 6},
            {"Sora", 287, 100, 7, 45, 67, 98, 23, 15, false, {}, 4},
        };

        channels_ = {
            {"#general", 234, 126, 38, "Mina", 7, 1.0},
            {"#dev", 203, 132, 44, "Tate", 6, 1.2},
            {"#random", 178, 101, 33, "Ken", 5, 0.8},
            {"#agri", 167, 109, 36, "Tate", 4, 1.2},
            {"#governance", 142, 84, 29, "Haru", 5, 1.0},
            {"#learning", 98, 64, 21, "Aoi", 4, 1.2},
            {"#book-commons", 76, 47, 16, "Aoi", 3, 1.2},
            {"#music", 45, 25, 8, "Yuu", 2, 0.8}
        };

        votes_ = {
            {"007", "Deploy Comm0ns Scoring v2", "major", 18, 3, 6, 8, 5},
            {"008", "Create #cooking channel", "normal", 12, 5, 5, 8, 2}
        };

        issues_ = {
            {42, "Improve bot response latency", "bug", "high", "review", "Riku"},
            {43, "Fix title layout overflow", "bug", "medium", "in-progress", "Tate"},
            {44, "Auto-generate monthly reports", "feature", "low", "open", "-"},
            {45, "Migrate to PostgREST 12", "ops", "high", "in-progress", "@fumi"},
        };

        feed_ = {
            {"ACHV", "Tate", "earned title: Contributor"},
            {"VOTE", "Haru", "created major vote #007"},
            {"QEST", "Ken", "quest cleared: logo refresh (+50)"},
            {"INFO", "Aoi", "shared AI paper in #learning (+5)"},
            {"STRK", "Tate", "30-day streak bonus (+15)"},
            {"ISSU", "Riku", "closed issue #42"},
            {"OPS", "Riku", "posted sprint cadence update (+4)"},
            {"INSI", "Haru", "policy analysis accepted (+4)"}
        };

        samples_ = {
            {"#learning", "https://arxiv.org/abs/2501.00001 Great benchmark summary."},
            {"#governance", "Please vote by Friday. We need quorum for major proposal."},
            {"#general", "nice!"},
            {"#dev", "I benchmarked two caching strategies and variant B lowered p95 latency by 37%."},
            {"#random", "lol"},
            {"#article-share", "A practical guide for DAOs with governance case studies."},
        };

        sprint_ = {"Sprint-3", "2026-03-01", "2026-03-14", {42, 43, 45}, 20};
    }

    // Legacy mock histories (kept for reference, currently disabled).
    void init_mock_histories() {
        std::uniform_int_distribution<int> total_d(20, 70);
        std::uniform_int_distribution<int> info_d(4, 25);
        std::uniform_int_distribution<int> insight_d(4, 24);
        std::uniform_int_distribution<int> vibe_d(6, 30);
        std::uniform_int_distribution<int> ops_d(3, 18);

        total_hist_.resize(kHistoryWidth);
        info_hist_.resize(kHistoryWidth);
        insight_hist_.resize(kHistoryWidth);
        vibe_hist_.resize(kHistoryWidth);
        ops_hist_.resize(kHistoryWidth);

        for (int i = 0; i < kHistoryWidth; ++i) {
            total_hist_[i] = total_d(rng_);
            info_hist_[i] = info_d(rng_);
            insight_hist_[i] = insight_d(rng_);
            vibe_hist_[i] = vibe_d(rng_);
            ops_hist_[i] = ops_d(rng_);
        }
    }

    bool load_from_db() {
        const QueryResult users_q = query_supabase(
            "users",
            {"select=user_id,username,current_score,weekly_score", "order=current_score.desc", "limit=300"},
            ".[] | [(.user_id|tostring), (.username // \"\"), (.current_score|tostring), (.weekly_score|tostring)] | @tsv"
        );
        if (!users_q.ok) {
            last_error_ = "users query failed: " + users_q.error;
            return false;
        }

        members_.clear();
        channels_.clear();
        votes_.clear();
        issues_.clear();
        feed_.clear();
        samples_.clear();
        user_name_by_id_.clear();
        channel_name_by_id_.clear();

        std::unordered_map<long long, size_t> member_idx_by_id;
        for (const auto& row : users_q.rows) {
            if (row.size() < 4) {
                continue;
            }
            const long long uid = to_ll(row[0], 0);
            if (uid == 0) {
                continue;
            }
            std::string username = row[1];
            if (username.empty()) {
                username = "user-" + std::to_string(uid);
            }
            Member m{};
            m.name = username;
            m.cp = std::max(0, static_cast<int>(std::round(to_double(row[2], 0.0))));
            m.ts = 100;
            m.streak = 0;
            m.info = 0;
            m.insight = 0;
            m.vibe = 0;
            m.ops = 0;
            m.misc = 0;
            m.online = false;
            m.votes_participated = 0;
            members_.push_back(m);
            member_idx_by_id[uid] = members_.size() - 1;
            user_name_by_id_[uid] = username;
        }

        const QueryResult member_ts_q = query_supabase(
            "members",
            {"select=*", "limit=1000"},
            ".[] | [((.user_id // .member_id // .discord_user_id // .id // 0)|tostring), ((.ts // .trust_score // .ts_score // .trust // 100)|tostring)] | @tsv"
        );
        members_table_available_ = member_ts_q.ok;
        if (member_ts_q.ok) {
            for (const auto& row : member_ts_q.rows) {
                if (row.size() < 2) {
                    continue;
                }
                const long long uid = to_ll(row[0], 0);
                auto it = member_idx_by_id.find(uid);
                if (it == member_idx_by_id.end()) {
                    continue;
                }
                members_[it->second].ts = clampi(static_cast<int>(std::round(to_double(row[1], 100.0))), 0, 100);
            }
        }

        const QueryResult channels_q = query_supabase(
            "channels",
            {"select=channel_id,name", "limit=3000"},
            ".[] | [(.channel_id|tostring), (.name // \"\")] | @tsv"
        );
        if (channels_q.ok) {
            for (const auto& row : channels_q.rows) {
                if (row.size() < 2) {
                    continue;
                }
                const long long cid = to_ll(row[0], 0);
                if (cid == 0) {
                    continue;
                }
                channel_name_by_id_[cid] = normalize_channel_label(row[1], cid);
            }
        }

        const QueryResult messages_q = query_supabase(
            "messages",
            {"select=message_id,user_id,channel_id,content,timestamp", "order=timestamp.desc", "limit=6000"},
            ".[] | [(.message_id|tostring), (.user_id|tostring), (.channel_id|tostring), (.content // \"\"), (.timestamp // \"\")] | @tsv"
        );

        std::unordered_map<long long, long long> message_owner;
        std::unordered_map<long long, int> channel_message_count;
        std::unordered_map<long long, int> channel_message_count_month;
        std::unordered_map<long long, int> channel_message_count_week;
        std::unordered_map<long long, std::unordered_map<long long, int>> channel_user_counts;
        std::unordered_map<long long, std::unordered_set<long long>> channel_active_users;
        std::unordered_map<long long, std::set<int>> active_days_by_user;
        std::unordered_map<long long, int> reaction_count_today;
        std::map<int, int> daily_total;
        std::map<int, int> daily_info;
        std::map<int, int> daily_insight;
        std::map<int, int> daily_vibe;
        std::map<int, int> daily_ops;
        std::map<int, int> pulse_total;

        auto find_member = [&](long long uid) -> Member* {
            auto it = member_idx_by_id.find(uid);
            if (it == member_idx_by_id.end()) {
                return nullptr;
            }
            return &members_[it->second];
        };

        auto type_for_category = [](Category c) {
            switch (c) {
                case Category::Info: return std::string("INFO");
                case Category::Insight: return std::string("INSI");
                case Category::Vibe: return std::string("VIBE");
                case Category::Ops: return std::string("OPS");
                case Category::Misc: return std::string("MISC");
            }
            return std::string("MISC");
        };

        const int today_serial = today_day_serial();
        if (messages_q.ok) {
            for (const auto& row : messages_q.rows) {
                if (row.size() < 5) {
                    continue;
                }
                const long long message_id = to_ll(row[0], 0);
                const long long user_id = to_ll(row[1], 0);
                const long long channel_id = to_ll(row[2], 0);
                if (user_id == 0 || channel_id == 0 || message_id == 0) {
                    continue;
                }
                const std::string channel_name = normalize_channel_label(
                    channel_name_by_id_.count(channel_id) ? channel_name_by_id_[channel_id] : "",
                    channel_id
                );
                const std::string content = row[3];
                const std::optional<int> day = parse_day_serial(row[4]);
                const RuleResult result = rule_based_classify({channel_name, content});
                Member* member = find_member(user_id);
                if (member) {
                    switch (result.category) {
                        case Category::Info: ++member->info; break;
                        case Category::Insight: ++member->insight; break;
                        case Category::Vibe: ++member->vibe; break;
                        case Category::Ops: ++member->ops; break;
                        case Category::Misc: ++member->misc; break;
                    }
                }

                if (samples_.size() < 10 && !content.empty()) {
                    samples_.push_back({channel_name, content});
                }
                if (feed_.size() < 14) {
                    const std::string user_name = user_name_by_id_.count(user_id) ? user_name_by_id_[user_id] : ("user-" + std::to_string(user_id));
                    const std::string message = !content.empty() ? fit(content, 44) : ("posted in " + channel_name);
                    feed_.push_back({type_for_category(result.category), user_name, message});
                }

                message_owner[message_id] = user_id;
                channel_message_count[channel_id] += 1;
                channel_user_counts[channel_id][user_id] += 1;
                channel_active_users[channel_id].insert(user_id);

                if (day) {
                    if (*day >= (today_serial - 29)) {
                        channel_message_count_month[channel_id] += 1;
                    }
                    if (*day >= (today_serial - 6)) {
                        channel_message_count_week[channel_id] += 1;
                    }
                    active_days_by_user[user_id].insert(*day);
                    if (*day == today_serial && member) {
                        member->online = true;
                    }
                    daily_total[*day] += 1;
                    switch (result.category) {
                        case Category::Info: daily_info[*day] += 1; break;
                        case Category::Insight: daily_insight[*day] += 1; break;
                        case Category::Vibe: daily_vibe[*day] += 1; break;
                        case Category::Ops: daily_ops[*day] += 1; break;
                        case Category::Misc: break;
                    }
                }
            }
        }

        const QueryResult reactions_q = query_supabase(
            "reactions",
            {"select=message_id,user_id,created_at", "order=created_at.desc", "limit=6000"},
            ".[] | [(.message_id|tostring), (.user_id|tostring), (.created_at // \"\")] | @tsv"
        );
        if (reactions_q.ok) {
            for (const auto& row : reactions_q.rows) {
                if (row.size() < 3) {
                    continue;
                }
                const long long message_id = to_ll(row[0], 0);
                const long long reactor_id = to_ll(row[1], 0);
                if (reactor_id == 0) {
                    continue;
                }
                Member* reactor = find_member(reactor_id);
                if (reactor) {
                    reactor->votes_participated += 1;
                }
                const std::optional<int> day = parse_day_serial(row[2]);
                if (day) {
                    active_days_by_user[reactor_id].insert(*day);
                    if (*day == today_serial) {
                        reaction_count_today[reactor_id] += 1;
                        if (reactor) {
                            reactor->online = true;
                        }
                    }
                }
            }
        }

        for (const auto& it : member_idx_by_id) {
            const long long uid = it.first;
            Member& member = members_[it.second];
            const auto days_it = active_days_by_user.find(uid);
            if (days_it == active_days_by_user.end() || days_it->second.empty()) {
                continue;
            }
            const std::set<int>& day_set = days_it->second;
            int streak = 0;
            int cursor = today_serial;
            while (day_set.find(cursor) != day_set.end()) {
                ++streak;
                --cursor;
            }
            member.streak = streak;
            if (streak >= 30) {
                member.titles.push_back("Streak-30");
            } else if (streak >= 7) {
                member.titles.push_back("Streak-7");
            }
            if (member.cp >= 1000) {
                member.titles.push_back("Top-CP");
            }
        }

        const QueryResult pulse_q = query_supabase(
            "analytics_daily_pulse",
            {"select=day,total_messages", "order=day.desc", "limit=60"},
            ".[] | [(.day|tostring), (.total_messages|tostring)] | @tsv"
        );
        if (pulse_q.ok) {
            for (const auto& row : pulse_q.rows) {
                if (row.size() < 2) {
                    continue;
                }
                const std::optional<int> day = parse_day_serial(row[0]);
                if (!day) {
                    continue;
                }
                pulse_total[*day] = to_int(row[1], 0);
            }
        }

        const QueryResult channel_leaders_q = query_supabase(
            "analytics_channel_leader_user",
            {"select=channel_id,username"},
            ".[] | [(.channel_id|tostring), (.username // \"-\")] | @tsv"
        );
        std::unordered_map<long long, std::string> champion_name_by_channel;
        if (channel_leaders_q.ok) {
            for (const auto& row : channel_leaders_q.rows) {
                if (row.size() < 2) {
                    continue;
                }
                const long long channel_id = to_ll(row[0], 0);
                champion_name_by_channel[channel_id] = row[1].empty() ? "-" : row[1];
            }
        }

        const QueryResult channel_ranking_q = query_supabase(
            "analytics_channel_ranking",
            {"select=channel_id,channel_name,total_messages,active_users", "order=total_messages.desc", "limit=120"},
            ".[] | [(.channel_id|tostring), (.channel_name // \"\"), (.total_messages|tostring), (.active_users|tostring)] | @tsv"
        );
        if (channel_ranking_q.ok) {
            for (const auto& row : channel_ranking_q.rows) {
                if (row.size() < 4) {
                    continue;
                }
                const long long channel_id = to_ll(row[0], 0);
                const std::string channel_name = normalize_channel_label(row[1], channel_id);
                channels_.push_back({
                    channel_name,
                    std::max(0, to_int(row[2], 0)),
                    std::max(0, channel_message_count_month[channel_id]),
                    std::max(0, channel_message_count_week[channel_id]),
                    champion_name_by_channel.count(channel_id) ? champion_name_by_channel[channel_id] : "-",
                    std::max(0, to_int(row[3], 0)),
                    channel_weight(channel_name)
                });
            }
        }

        if (channels_.empty()) {
            for (const auto& it : channel_message_count) {
                const long long channel_id = it.first;
                const std::string channel_name = normalize_channel_label(
                    channel_name_by_id_.count(channel_id) ? channel_name_by_id_[channel_id] : "",
                    channel_id
                );
                std::string champion = "-";
                int top_count = 0;
                auto uc_it = channel_user_counts.find(channel_id);
                if (uc_it != channel_user_counts.end()) {
                    for (const auto& kv : uc_it->second) {
                        if (kv.second > top_count) {
                            top_count = kv.second;
                            champion = user_name_by_id_.count(kv.first) ? user_name_by_id_[kv.first] : ("user-" + std::to_string(kv.first));
                        }
                    }
                }
                channels_.push_back({
                    channel_name,
                    std::max(0, it.second),
                    std::max(0, channel_message_count_month[channel_id]),
                    std::max(0, channel_message_count_week[channel_id]),
                    champion,
                    static_cast<int>(channel_active_users[channel_id].size()),
                    channel_weight(channel_name)
                });
            }
            std::sort(channels_.begin(), channels_.end(), [](const Channel& a, const Channel& b) {
                return a.messages_total > b.messages_total;
            });
        }

        const QueryResult votes_q = query_supabase(
            "votes",
            {"select=*", "limit=30"},
            ".[] | [((.id // .vote_id // .proposal_id // 0)|tostring), ((.title // .name // \"(untitled)\")|tostring), ((.type // .vote_type // \"normal\")|tostring), ((.yes_vp // .yes_votes // .yes // 0)|tostring), ((.no_vp // .no_votes // .no // 0)|tostring), ((.voters // .voter_count // 0)|tostring), ((.total_eligible // .eligible_voters // .eligible // 0)|tostring), ((.days_left // .remaining_days // 0)|tostring)] | @tsv"
        );
        votes_table_available_ = votes_q.ok;
        if (votes_q.ok) {
            for (const auto& row : votes_q.rows) {
                if (row.size() < 8) {
                    continue;
                }
                votes_.push_back({
                    row[0],
                    row[1],
                    row[2],
                    std::max(0, to_int(row[3], 0)),
                    std::max(0, to_int(row[4], 0)),
                    std::max(0, to_int(row[5], 0)),
                    std::max(0, to_int(row[6], 0)),
                    std::max(0, to_int(row[7], 0))
                });
            }
        }

        const QueryResult issues_q = query_supabase(
            "issues",
            {"select=*", "limit=50"},
            ".[] | [((.id // .issue_id // 0)|tostring), ((.title // .name // \"(untitled)\")|tostring), ((.label // .type // \"-\")|tostring), ((.priority // \"medium\")|tostring), ((.status // \"open\")|tostring), ((.assignee // .owner // \"-\")|tostring)] | @tsv"
        );
        issues_table_available_ = issues_q.ok;
        if (issues_q.ok) {
            for (const auto& row : issues_q.rows) {
                if (row.size() < 6) {
                    continue;
                }
                issues_.push_back({
                    std::max(0, to_int(row[0], 0)),
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5]
                });
            }
        }

        total_hist_.assign(kHistoryWidth, 0);
        info_hist_.assign(kHistoryWidth, 0);
        insight_hist_.assign(kHistoryWidth, 0);
        vibe_hist_.assign(kHistoryWidth, 0);
        ops_hist_.assign(kHistoryWidth, 0);
        for (int i = 0; i < kHistoryWidth; ++i) {
            const int day = today_serial - (kHistoryWidth - 1 - i);
            total_hist_[i] = pulse_total.count(day) ? pulse_total[day] : daily_total[day];
            info_hist_[i] = daily_info[day];
            insight_hist_[i] = daily_insight[day];
            vibe_hist_[i] = daily_vibe[day];
            ops_hist_[i] = daily_ops[day];
        }

        if (samples_.empty()) {
            samples_.push_back({"#general", "No recent messages in DB. (messages table empty)"});
        }
        if (feed_.empty()) {
            feed_.push_back({"INFO", "system", "No recent activity records."});
        }

        std::vector<int> sprint_issue_ids;
        for (size_t i = 0; i < issues_.size() && i < 3; ++i) {
            sprint_issue_ids.push_back(issues_[i].id);
        }
        sprint_ = {
            "Current Sprint",
            iso_date_from_serial(today_serial),
            iso_date_from_serial(today_serial + 13),
            sprint_issue_ids,
            20
        };

        db_ready_ = true;
        using_mock_data_ = false;
        data_status_ = "DB LIVE";
        last_refresh_hms_ = now_hms();
        last_error_.clear();
        last_db_refresh_ = std::chrono::steady_clock::now();
        return true;
    }

    void refresh_from_db(bool manual_trigger) {
        const char* url = std::getenv("SUPABASE_URL");
        const char* key = std::getenv("SUPABASE_KEY");
        if (!url || !key || std::string(url).empty() || std::string(key).empty()) {
            using_mock_data_ = false;
            data_status_ = "DB ERROR";
            last_error_ = manual_trigger
                ? "SUPABASE_URL / SUPABASE_KEY が未設定です。"
                : "SUPABASE_URL / SUPABASE_KEY が未設定のため DB 接続できません。";
            return;
        }

        if (!load_from_db()) {
            if (db_ready_) {
                data_status_ = "DB STALE";
            } else {
                using_mock_data_ = false;
                data_status_ = "DB ERROR";
            }
        }
    }

    void tick() {
        const auto now = std::chrono::steady_clock::now();
        if (now - last_db_refresh_ >= std::chrono::seconds(db_refresh_interval_sec_)) {
            if (!load_from_db()) {
                data_status_ = db_ready_ ? "DB STALE" : "DB ERROR";
            }
        }

        // Mock animation branch is intentionally preserved but disabled.
        // if (using_mock_data_) {
        //     auto push_rw = [&](std::vector<int>& hist, int lo, int hi, int delta) {
        //         const int last = hist.empty() ? lo : hist.back();
        //         std::uniform_int_distribution<int> move(-delta, delta);
        //         int next = clampi(last + move(rng_), lo, hi);
        //         hist.erase(hist.begin());
        //         hist.push_back(next);
        //     };
        //     push_rw(total_hist_, 10, 80, 8);
        //     push_rw(info_hist_, 2, 26, 3);
        //     push_rw(insight_hist_, 2, 28, 3);
        //     push_rw(vibe_hist_, 4, 34, 4);
        //     push_rw(ops_hist_, 1, 18, 3);
        // }
    }

    std::vector<int> sorted_member_indices() const {
        std::vector<int> idx(members_.size());
        std::iota(idx.begin(), idx.end(), 0);

        auto key_of = [&](const Member& m) {
            switch (sort_key_) {
                case SortKey::Cp: return static_cast<double>(m.cp);
                case SortKey::Ts: return static_cast<double>(m.ts);
                case SortKey::Vp: return static_cast<double>(calc_vp(m.cp));
                case SortKey::Streak: return static_cast<double>(m.streak);
                case SortKey::Info: return static_cast<double>(m.info);
                case SortKey::Insight: return static_cast<double>(m.insight);
                case SortKey::Vibe: return static_cast<double>(m.vibe);
                case SortKey::Ops: return static_cast<double>(m.ops);
            }
            return static_cast<double>(m.cp);
        };

        std::sort(idx.begin(), idx.end(), [&](int lhs, int rhs) {
            const Member& a = members_[lhs];
            const Member& b = members_[rhs];
            double ka = key_of(a);
            double kb = key_of(b);
            if (ka == kb) {
                return a.cp > b.cp;
            }
            return ka > kb;
        });

        return idx;
    }

    int channel_messages_for_range(const Channel& ch) const {
        switch (channel_activity_range_) {
            case ChannelActivityRange::All: return ch.messages_total;
            case ChannelActivityRange::Month: return ch.messages_month;
            case ChannelActivityRange::Week: return ch.messages_week;
        }
        return ch.messages_total;
    }

    std::string channel_range_label() const {
        switch (channel_activity_range_) {
            case ChannelActivityRange::All: return "TOTAL";
            case ChannelActivityRange::Month: return "MONTH";
            case ChannelActivityRange::Week: return "WEEK";
        }
        return "TOTAL";
    }

    std::vector<const Channel*> sorted_channels_for_activity() const {
        std::vector<const Channel*> ordered;
        ordered.reserve(channels_.size());
        for (const auto& ch : channels_) {
            ordered.push_back(&ch);
        }
        std::sort(ordered.begin(), ordered.end(), [&](const Channel* lhs, const Channel* rhs) {
            const int left = channel_messages_for_range(*lhs);
            const int right = channel_messages_for_range(*rhs);
            if (left != right) {
                return left > right;
            }
            if (lhs->messages_total != rhs->messages_total) {
                return lhs->messages_total > rhs->messages_total;
            }
            return lhs->name < rhs->name;
        });
        return ordered;
    }

    void draw() {
        erase();

        int h = 0;
        int w = 0;
        getmaxyx(stdscr, h, w);

        if (h < kMinHeight || w < kMinWidth) {
            draw_too_small(h, w);
            refresh();
            return;
        }

        draw_topbar(w);
        draw_footer(h, w);

        const int content_y = 1;
        const int content_h = h - 3;

        switch (page_) {
            case 1: draw_overview(content_y, content_h, w); break;
            case 2: draw_members(content_y, content_h, w); break;
            case 3: draw_channels(content_y, content_h, w); break;
            case 4: draw_governance(content_y, content_h, w); break;
            case 5: draw_issues(content_y, content_h, w); break;
            default: draw_overview(content_y, content_h, w); break;
        }

        refresh();
    }

    void draw_too_small(int h, int w) {
        attron(COLOR_PAIR(5) | A_BOLD);
        mvprintw(1, 2, "Terminal too small for comm0ns-cpp-tui");
        attroff(COLOR_PAIR(5) | A_BOLD);
        mvprintw(3, 2, "Current: %dx%d", w, h);
        mvprintw(4, 2, "Required: >= %dx%d", kMinWidth, kMinHeight);
        mvprintw(6, 2, "Resize and keep running, or press q to quit.");
    }

    void draw_topbar(int w) {
        const std::array<std::string, 5> tabs = {
            "1:Overview",
            "2:Members",
            "3:Channels",
            "4:Governance",
            "5:Issues"
        };

        tab_hits_.clear();
        int x = 1;
        for (size_t i = 0; i < tabs.size(); ++i) {
            const bool active = static_cast<int>(i + 1) == page_;
            attr_t attr = COLOR_PAIR(active ? 8 : 7);
            if (active) attr |= A_BOLD;
            attron(attr);
            const std::string label = " " + tabs[i] + " ";
            mvaddnstr(0, x, label.c_str(), w - x - 1);
            attroff(attr);
            tab_hits_.push_back({x, x + static_cast<int>(label.size()) - 1, static_cast<int>(i + 1)});
            x += static_cast<int>(label.size()) + 1;
        }

        std::string right = "comm0ns-cpp-tui [" + data_status_ + "] " + now_hms();
        if (!last_refresh_hms_.empty() && last_refresh_hms_ != "-") {
            right += "  ref:" + last_refresh_hms_;
        }
        put_line(0, std::max(1, w - static_cast<int>(right.size()) - 2), static_cast<int>(right.size()), right, 2, true);
    }

    void handle_mouse() {
        MEVENT event{};
        if (getmouse(&event) != OK) {
            return;
        }
        if (!(event.bstate & (BUTTON1_CLICKED | BUTTON1_DOUBLE_CLICKED | BUTTON1_PRESSED | BUTTON1_RELEASED))) {
            return;
        }
        if (event.y == 0) {
            for (const auto& hit : tab_hits_) {
                if (event.x >= hit.x0 && event.x <= hit.x1) {
                    page_ = hit.page;
                    return;
                }
            }
        }

        if (page_ == 2) {
            for (const auto& hit : member_row_hits_) {
                if (event.y == hit.y && event.x >= hit.x0 && event.x <= hit.x1) {
                    selected_member_row_ = hit.row_index;
                    return;
                }
            }
        }

        if (page_ == 3) {
            for (const auto& hit : channel_range_hits_) {
                if (event.y == hit.y && event.x >= hit.x0 && event.x <= hit.x1) {
                    channel_activity_range_ = hit.range;
                    return;
                }
            }
        }
    }

    void draw_footer(int h, int w) {
        const std::string left = "j/k:select  s:sort  a/m/w:ch-range  r:refresh  1-5:page  q:quit";
        const std::string right = "Design: Stage1/2/3 + CP*TS + VP(log2) + Vote/Issue/Titles";
        put_line(h - 1, 1, w - 2, left, 7, false);
        put_line(h - 1, std::max(1, w - static_cast<int>(right.size()) - 2), static_cast<int>(right.size()), right, 7, false);
    }

    void draw_overview(int y, int h, int w) {
        const int row1_h = h / 2;
        const int row2_h = h - row1_h;
        const int left_w = (w * 2) / 3;
        const int right_w = w - left_w;

        draw_box(y, 0, row1_h, left_w, " Activity Engine ", 2);
        draw_box(y, left_w, row1_h, right_w, " Community Stats ", 3);
        draw_box(y + row1_h, 0, row2_h, w / 2, " Live Feed ", 6);
        draw_box(y + row1_h, w / 2, row2_h, w - w / 2, " Category + Rewards ", 4);

        draw_overview_activity(y + 1, 2, row1_h - 2, left_w - 4);
        draw_overview_stats(y + 1, left_w + 2, row1_h - 2, right_w - 4);
        draw_overview_feed(y + row1_h + 1, 2, row2_h - 2, w / 2 - 4);
        draw_overview_category(y + row1_h + 1, w / 2 + 2, row2_h - 2, w - (w / 2) - 4);
    }

    void draw_overview_activity(int y, int x, int h, int w) {
        if (h <= 0) return;

        int line = y;
        put_line(line++, x, w, "TOTAL    [" + bar(total_hist_.back(), 80, 26) + "] " + std::to_string(total_hist_.back()) + " msg/h", 3);
        put_line(line++, x, w, "INFO     [" + bar(info_hist_.back(), 26, 26) + "] " + std::to_string(info_hist_.back()), 2);
        put_line(line++, x, w, "INSIGHT  [" + bar(insight_hist_.back(), 28, 26) + "] " + std::to_string(insight_hist_.back()), 9);
        put_line(line++, x, w, "VIBE     [" + bar(vibe_hist_.back(), 34, 26) + "] " + std::to_string(vibe_hist_.back()), 6);
        put_line(line++, x, w, "OPS      [" + bar(ops_hist_.back(), 18, 26) + "] " + std::to_string(ops_hist_.back()), 4);

        if (line < y + h) {
            put_line(line++, x, w, "", 1);
        }

        int stage1 = 0;
        int stage2 = 0;
        int low_conf = 0;
        for (const auto& sample : samples_) {
            RuleResult r = rule_based_classify(sample);
            if (r.stage == 1) ++stage1; else ++stage2;
            if (r.confidence > 0.0 && r.confidence < 0.60) ++low_conf;
        }

        put_line(line++, x, w, "Pipeline: Stage1=" + std::to_string(stage1) + "  Stage2Queue=" + std::to_string(stage2), 1);
        if (line < y + h) {
            put_line(line++, x, w, "Review queue (<0.60 conf): " + std::to_string(low_conf), 4);
        }
        if (line < y + h) {
            put_line(line++, x, w, "Formula: effectiveCP = baseCP * channelWeight * (TS/100)", 7);
        }
    }

    void draw_overview_stats(int y, int x, int h, int w) {
        if (h <= 0) return;
        int total_cp = 0;
        int avg_ts_sum = 0;
        int online = 0;
        int total_vp = 0;
        int titles_total = 0;

        for (const auto& m : members_) {
            total_cp += m.cp;
            avg_ts_sum += m.ts;
            if (m.online) ++online;
            total_vp += calc_effective_vp(m);
            titles_total += static_cast<int>(m.titles.size());
        }

        const double avg_ts = members_.empty() ? 0.0 : static_cast<double>(avg_ts_sum) / static_cast<double>(members_.size());

        int open_issues = 0;
        for (const auto& issue : issues_) {
            if (issue.status != "closed") ++open_issues;
        }

        int line = y;
        put_line(line++, x, w, "Total effective CP : " + std::to_string(total_cp), 3, true);
        put_line(line++, x, w, "Members online     : " + std::to_string(online) + "/" + std::to_string(members_.size()), 2);
        put_line(line++, x, w, "Average TS         : " + format_double(avg_ts, 1), 4);
        put_line(line++, x, w, "Total effective VP : " + std::to_string(total_vp), 9);
        put_line(line++, x, w, "Open Issues        : " + std::to_string(open_issues), 5);
        put_line(line++, x, w, "Active Votes       : " + std::to_string(votes_.size()), 6);
        put_line(line++, x, w, "Titles awarded     : " + std::to_string(titles_total), 1);
        if (line < y + h) {
            put_line(line++, x, w, "Data source        : " + (using_mock_data_ ? std::string("mock") : std::string("supabase")), 7);
        }
        if (!last_error_.empty() && line < y + h) {
            put_line(line++, x, w, fit("Last error: " + last_error_, w), 5);
        }

        if (line < y + h) {
            put_line(line++, x, w, "", 1);
        }
        if (line < y + h) {
            put_line(line++, x, w, "VP = floor(log2(cumulativeEffectiveCP + 1)) + 1", 7);
        }
        if (line < y + h) {
            put_line(line++, x, w, "effectiveVP = floor(VP * TS/100), min 1, max VP 6", 7);
        }
    }

    void draw_overview_feed(int y, int x, int h, int w) {
        int max_rows = std::min(h, static_cast<int>(feed_.size()));
        for (int i = 0; i < max_rows; ++i) {
            const auto& f = feed_[i];
            std::ostringstream oss;
            oss << std::setw(2) << i + 1 << "m " << std::left << std::setw(4) << f.type << " "
                << std::setw(5) << f.user << " " << f.message;
            put_line(y + i, x, w, fit(oss.str(), w), color_for_feed(f.type));
        }
    }

    void draw_overview_category(int y, int x, int h, int w) {
        int sum_info = 0;
        int sum_insight = 0;
        int sum_vibe = 0;
        int sum_ops = 0;
        int sum_misc = 0;

        for (const auto& m : members_) {
            sum_info += m.info;
            sum_insight += m.insight;
            sum_vibe += m.vibe;
            sum_ops += m.ops;
            sum_misc += m.misc;
        }

        const int max_val = std::max({sum_info, sum_insight, sum_vibe, sum_ops, sum_misc, 1});

        int line = y;
        put_line(line++, x, w, "INFO    [" + bar(sum_info, max_val, 22) + "] " + std::to_string(sum_info), 2);
        put_line(line++, x, w, "INSIGHT [" + bar(sum_insight, max_val, 22) + "] " + std::to_string(sum_insight), 9);
        put_line(line++, x, w, "VIBE    [" + bar(sum_vibe, max_val, 22) + "] " + std::to_string(sum_vibe), 6);
        put_line(line++, x, w, "OPS     [" + bar(sum_ops, max_val, 22) + "] " + std::to_string(sum_ops), 4);
        put_line(line++, x, w, "MISC    [" + bar(sum_misc, max_val, 22) + "] " + std::to_string(sum_misc), 7);

        if (line < y + h) {
            put_line(line++, x, w, "", 1);
        }
        if (line < y + h) {
            put_line(line++, x, w, "Streak bonus tiers: 3d:+2  7d:+5  30d:+15", 1);
        }
    }

    void draw_members(int y, int h, int w) {
        const int left_w = (w * 3) / 5;
        const int right_w = w - left_w;

        draw_box(y, 0, h, left_w, " Members Table ", 6);
        draw_box(y, left_w, h, right_w, " Selected Member ", 2);

        draw_members_table(y + 1, 2, h - 2, left_w - 4);
        draw_member_detail(y + 1, left_w + 2, h - 2, right_w - 4);
    }

    void draw_members_table(int y, int x, int h, int w) {
        const auto sorted = sorted_member_indices();
        const int row_count = static_cast<int>(sorted.size());
        selected_member_row_ = clampi(selected_member_row_, 0, std::max(0, row_count - 1));
        member_row_hits_.clear();

        const int col_on = 2;
        const int col_name = 10;
        const int col_cp = 5;
        const int col_ts = 4;
        const int col_vp = 2;
        const int col_stk = 3;
        const int col_info = 4;
        const int col_insi = 4;
        const int col_vibe = 4;
        const int col_ops = 3;
        const int col_cpp = 3;

        auto header_line = [&]() -> std::string {
            return pad_right_display("ON", col_on) + " " +
                   pad_right_display("NAME", col_name) + " " +
                   pad_left_display("CP", col_cp) + " " +
                   pad_left_display("TS", col_ts) + " " +
                   pad_left_display("VP", col_vp) + " " +
                   pad_left_display("STK", col_stk) + " " +
                   pad_left_display("INFO", col_info) + " " +
                   pad_left_display("INSI", col_insi) + " " +
                   pad_left_display("VIBE", col_vibe) + " " +
                   pad_left_display("OPS", col_ops) + " " +
                   pad_left_display("CP%", col_cpp);
        };

        auto row_line = [&](const Member& m, int vp, int cp_pct) -> std::string {
            return pad_right_display(m.online ? "*" : ".", col_on) + " " +
                   pad_right_display(m.name, col_name) + " " +
                   pad_left_display(std::to_string(m.cp), col_cp) + " " +
                   pad_left_display(std::to_string(m.ts), col_ts) + " " +
                   pad_left_display(std::to_string(vp), col_vp) + " " +
                   pad_left_display(std::to_string(m.streak), col_stk) + " " +
                   pad_left_display(std::to_string(m.info), col_info) + " " +
                   pad_left_display(std::to_string(m.insight), col_insi) + " " +
                   pad_left_display(std::to_string(m.vibe), col_vibe) + " " +
                   pad_left_display(std::to_string(m.ops), col_ops) + " " +
                   pad_left_display(std::to_string(cp_pct), col_cpp);
        };

        put_line(y, x, w, "Sort: " + sort_name(sort_key_) + "    Keys: s cycle, j/k select", 7);
        put_line(y + 1, x, w, header_line(), 7, true);

        int max_cp = 1;
        for (const auto& m : members_) {
            max_cp = std::max(max_cp, m.cp);
        }

        int table_y = y + 2;
        const int rows_avail = h - 2;
        for (int i = 0; i < rows_avail && i < row_count; ++i) {
            const Member& m = members_[sorted[i]];
            const bool selected = (i == selected_member_row_);
            if (selected) {
                attron(COLOR_PAIR(8));
                mvhline(table_y + i, x, ' ', w);
                attroff(COLOR_PAIR(8));
            }

            const int vp = calc_vp(m.cp);
            const int cp_pct = static_cast<int>(std::round((static_cast<double>(m.cp) / max_cp) * 100.0));
            put_line(table_y + i, x, w, fit(row_line(m, vp, cp_pct), w), selected ? 8 : 1, false);
            member_row_hits_.push_back({table_y + i, x, x + std::max(0, w - 1), i});
        }
    }

    void draw_member_detail(int y, int x, int h, int w) {
        const auto sorted = sorted_member_indices();
        if (sorted.empty()) return;

        selected_member_row_ = clampi(selected_member_row_, 0, static_cast<int>(sorted.size()) - 1);
        const Member& m = members_[sorted[selected_member_row_]];

        int line = y;
        put_line(line++, x, w, m.name + std::string(m.online ? " (online)" : " (offline)"), 2, true);
        put_line(line++, x, w, "CP=" + std::to_string(m.cp) + "  TS=" + std::to_string(m.ts) + "  VP=" + std::to_string(calc_vp(m.cp)), 3);
        put_line(line++, x, w, "Effective VP=" + std::to_string(calc_effective_vp(m)) + "  streak=" + std::to_string(m.streak) + "d", 4);

        if (!m.titles.empty() && line < y + h) {
            std::string all = "Titles: ";
            for (size_t i = 0; i < m.titles.size(); ++i) {
                if (i) all += ", ";
                all += m.titles[i];
            }
            put_line(line++, x, w, fit(all, w), 6);
        }

        if (line < y + h) put_line(line++, x, w, "", 1);

        const int total = std::max(1, m.info + m.insight + m.vibe + m.ops + m.misc);
        put_line(line++, x, w, "INFO    [" + bar(m.info, total, 20) + "] " + std::to_string((m.info * 100) / total) + "%", 2);
        put_line(line++, x, w, "INSIGHT [" + bar(m.insight, total, 20) + "] " + std::to_string((m.insight * 100) / total) + "%", 9);
        put_line(line++, x, w, "VIBE    [" + bar(m.vibe, total, 20) + "] " + std::to_string((m.vibe * 100) / total) + "%", 6);
        put_line(line++, x, w, "OPS     [" + bar(m.ops, total, 20) + "] " + std::to_string((m.ops * 100) / total) + "%", 4);
        put_line(line++, x, w, "MISC    [" + bar(m.misc, total, 20) + "] " + std::to_string((m.misc * 100) / total) + "%", 7);

        if (line < y + h) put_line(line++, x, w, "", 1);

        const int vp = calc_vp(m.cp);
        put_line(line++, x, w, "VP calc: floor(log2(" + std::to_string(m.cp) + "+1))+1 = " + std::to_string(vp), 7);
        put_line(line++, x, w, "effVP : floor(" + std::to_string(vp) + "*" + std::to_string(m.ts) + "/100) = " + std::to_string(calc_effective_vp(m)), 7);
    }

    void draw_channels(int y, int h, int w) {
        const int left_w = w / 2;
        const int right_w = w - left_w;

        draw_box(y, 0, h, left_w, " Channel Activity ", 3);
        draw_box(y, left_w, h, right_w, " Classification + Commands ", 9);

        draw_channels_left(y + 1, 2, h - 2, left_w - 4);
        draw_channels_right(y + 1, left_w + 2, h - 2, right_w - 4);
    }

    void draw_channels_left(int y, int x, int h, int w) {
        channel_range_hits_.clear();
        const auto ordered_channels = sorted_channels_for_activity();

        int max_msg = 1;
        for (const Channel* ch : ordered_channels) {
            max_msg = std::max(max_msg, channel_messages_for_range(*ch));
        }

        const int col_ch = 12;
        const int col_msg = 5;
        const int col_active = 3;
        const int col_weight = 4;
        const int col_champ = 10;
        const int fixed = col_ch + col_msg + col_active + col_weight + col_champ + 19;
        const int bar_w = std::max(8, std::min(16, w - fixed));
        const std::string msg_label = channel_range_label();

        auto header_line = [&]() -> std::string {
            return pad_right_display("CHANNEL", col_ch) + " " +
                   "[" + std::string(bar_w, '-') + "] " +
                   pad_left_display(msg_label, col_msg) + " " +
                   "A:" + pad_left_display("U", col_active) + " " +
                   "W:" + pad_left_display("x", col_weight) + " " +
                   "C:" + pad_right_display("CHAMP", col_champ);
        };

        auto row_line = [&](const Channel& ch) -> std::string {
            const int messages = channel_messages_for_range(ch);
            return pad_right_display(ch.name, col_ch) + " " +
                   "[" + bar(messages, max_msg, bar_w) + "] " +
                   pad_left_display(std::to_string(messages), col_msg) + " " +
                   "A:" + pad_left_display(std::to_string(ch.active_users), col_active) + " " +
                   "W:" + pad_left_display(format_double(ch.weight, 1), col_weight) + " " +
                   "C:" + pad_right_display(ch.champion, col_champ);
        };

        int line = y;
        if (line < y + h) {
            put_line(line, x, w, "Range:", 7, true);
            int cursor = x + 7;
            auto draw_range_chip = [&](ChannelActivityRange range, const std::string& label) {
                if (cursor >= x + w) {
                    return;
                }
                const bool active = (channel_activity_range_ == range);
                const std::string text = "[" + label + "]";
                const int avail = x + w - cursor;
                put_line(line, cursor, avail, text, active ? 8 : 7, active);
                const int visible = std::min(static_cast<int>(text.size()), avail);
                if (visible > 0) {
                    channel_range_hits_.push_back({line, cursor, cursor + visible - 1, range});
                }
                cursor += static_cast<int>(text.size()) + 1;
            };
            draw_range_chip(ChannelActivityRange::All, "All");
            draw_range_chip(ChannelActivityRange::Month, "Month");
            draw_range_chip(ChannelActivityRange::Week, "Week");
            ++line;
        }
        if (line < y + h) {
            put_line(line++, x, w, fit(header_line(), w), 7, true);
        }
        for (const Channel* ch : ordered_channels) {
            if (line >= y + h) break;
            int color = (ch->weight > 1.0) ? 3 : ((ch->weight < 1.0) ? 7 : 1);
            put_line(line++, x, w, fit(row_line(*ch), w), color);
        }

        if (line < y + h) put_line(line++, x, w, "", 1);
        if (line < y + h) put_line(line++, x, w, "Weight policy: project/knowledge x1.2, general x1.0, hobby x0.8", 7);
        if (line < y + h) put_line(line++, x, w, "VC points: +2 per 10min (cap configurable)", 7);
    }

    void draw_channels_right(int y, int x, int h, int w) {
        const int col_channel = 12;
        const int col_cat = 7;
        const int col_conf = 4;
        const int col_stage = 2;

        auto sample_header = [&]() -> std::string {
            return pad_right_display("CHANNEL", col_channel) + " " +
                   pad_right_display("CAT", col_cat) + " " +
                   "C:" + pad_left_display("0.00", col_conf) + " " +
                   "S:" + pad_left_display("1", col_stage);
        };

        auto sample_row = [&](const MessageSample& sample, const RuleResult& r) -> std::string {
            return pad_right_display(sample.channel, col_channel) + " " +
                   pad_right_display(category_name(r.category), col_cat) + " " +
                   "C:" + pad_left_display(format_double(r.confidence, 2), col_conf) + " " +
                   "S:" + pad_left_display(std::to_string(r.stage), col_stage);
        };

        auto command_row = [&](const std::string& c1, const std::string& c2, const std::string& c3 = "") -> std::string {
            return pad_right_display(c1, 11) + " " +
                   pad_right_display(c2, 14) + " " +
                   pad_right_display(c3, 14);
        };

        int line = y;
        put_line(line++, x, w, "Stage1 rule classification samples:", 7, true);
        if (line < y + h) {
            put_line(line++, x, w, fit(sample_header(), w), 7, true);
        }

        for (const auto& sample : samples_) {
            if (line >= y + h) break;
            RuleResult r = rule_based_classify(sample);
            put_line(line++, x, w, fit(sample_row(sample, r), w), (r.stage == 1 ? 2 : 4));
        }

        if (line < y + h) put_line(line++, x, w, "", 1);
        if (line < y + h) put_line(line++, x, w, "Slash command surface from spec:", 7, true);
        if (line < y + h) put_line(line++, x, w, fit(command_row("/mystats", "/leaderboard", "/history"), w), 1);
        if (line < y + h) put_line(line++, x, w, fit(command_row("/mytitles", "/settitle", "/vote create"), w), 1);
        if (line < y + h) put_line(line++, x, w, fit(command_row("/vote list", "/issue create", "/issue list"), w), 1);
        if (line < y + h) put_line(line++, x, w, fit(command_row("/quest create", "/dispute"), w), 1);

        if (line < y + h) put_line(line++, x, w, "", 1);
        if (line < y + h) {
            put_line(line++, x, w,
                fit(pad_right_display("members.ts", 14) + ": " + (members_table_available_ ? std::string("READY") : std::string("PENDING")), w),
                7);
        }
        if (line < y + h) {
            put_line(line++, x, w,
                fit(pad_right_display("votes", 14) + ": " + (votes_table_available_ ? std::string("READY") : std::string("PENDING")), w),
                7);
        }
        if (line < y + h) {
            put_line(line++, x, w,
                fit(pad_right_display("issues", 14) + ": " + (issues_table_available_ ? std::string("READY") : std::string("PENDING")), w),
                7);
        }
    }

    void draw_governance(int y, int h, int w) {
        const int left_w = (w * 3) / 5;
        const int right_w = w - left_w;

        draw_box(y, 0, h, left_w, " Votes ", 9);
        draw_box(y, left_w, h, right_w, " VP Distribution ", 4);

        draw_votes(y + 1, 2, h - 2, left_w - 4);
        draw_vp(y + 1, left_w + 2, h - 2, right_w - 4);
    }

    void draw_votes(int y, int x, int h, int w) {
        int line = y;
        if (votes_.empty()) {
            const std::string msg = votes_table_available_
                ? "No active votes in DB."
                : "votes table is not available (PENDING: create votes schema).";
            put_line(line++, x, w, fit(msg, w), votes_table_available_ ? 7 : 4, true);
            return;
        }
        for (const auto& v : votes_) {
            if (line >= y + h) break;
            const int total = std::max(1, v.yes_vp + v.no_vp);
            const double ratio = static_cast<double>(v.yes_vp) / static_cast<double>(total);
            const int turnout = static_cast<int>(std::round((static_cast<double>(v.voters) / std::max(1, v.total_eligible)) * 100.0));

            std::string rule = (v.type == "major") ? "need >=66% yes and turnout >=50%" : "need >50% yes";
            bool passed = false;
            if (v.type == "major") {
                passed = (ratio >= (2.0 / 3.0)) && (turnout >= 50);
            } else {
                passed = ratio > 0.5;
            }

            put_line(line++, x, w, "#" + v.id + " " + fit(v.title, std::max(10, w - 10)), 1, true);
            put_line(line++, x, w, "Y [" + bar(v.yes_vp, total, 30, '=') + "] " + std::to_string(v.yes_vp) + "VP", 3);
            put_line(line++, x, w, "N [" + bar(v.no_vp, total, 30, '=') + "] " + std::to_string(v.no_vp) + "VP", 5);

            std::ostringstream oss;
            oss << "yes=" << static_cast<int>(std::round(ratio * 100.0)) << "%  voters=" << v.voters << "/"
                << v.total_eligible << " (" << turnout << "%)  " << (passed ? "PASSED" : "PENDING")
                << "  " << v.days_left << "d left";
            put_line(line++, x, w, fit(oss.str(), w), passed ? 3 : 4);
            put_line(line++, x, w, fit("rule: " + rule, w), 7);
            if (line < y + h) put_line(line++, x, w, "", 1);
        }
    }

    void draw_vp(int y, int x, int h, int w) {
        int line = y;
        for (const auto& m : members_) {
            if (line >= y + h) break;
            const int vp = calc_vp(m.cp);
            const int evp = calc_effective_vp(m);
            std::ostringstream oss;
            oss << " " << (m.online ? '*' : '.')
                << " " << std::left << std::setw(6) << m.name
                << " VP[" << bar(vp, 6, 6, '=') << "] " << vp
                << " eff=" << evp
                << " TS=" << m.ts;
            put_line(line++, x, w, fit(oss.str(), w), m.online ? 1 : 7);
        }

        if (line < y + h) put_line(line++, x, w, "", 1);
        if (line < y + h) put_line(line++, x, w, "VP formula : floor(log2(cumulativeEffectiveCP+1))+1", 7);
        if (line < y + h) put_line(line++, x, w, "effectiveVP: floor(VP * TS/100), min 1", 7);
        if (line < y + h) put_line(line++, x, w, "Safety valve: if 50-66% in major vote, branch proposal allowed", 7);
    }

    void draw_issues(int y, int h, int w) {
        draw_box(y, 0, h, w, " Issue + Sprint Tracking ", 5);
        draw_issues_content(y + 1, 2, h - 2, w - 4);
    }

    void draw_issues_content(int y, int x, int h, int w) {
        int open = 0;
        int prog = 0;
        int review = 0;
        for (const auto& issue : issues_) {
            if (issue.status == "open") ++open;
            if (issue.status == "in-progress") ++prog;
            if (issue.status == "review") ++review;
        }

        int line = y;
        put_line(line++, x, w, "OPEN=" + std::to_string(open) + "  IN-PROGRESS=" + std::to_string(prog) +
                               "  REVIEW=" + std::to_string(review) + "  TOTAL=" + std::to_string(issues_.size()), 1, true);
        if (issues_.empty() && line < y + h) {
            const std::string msg = issues_table_available_
                ? "No issues in DB."
                : "issues table is not available (PENDING: create issues schema).";
            put_line(line++, x, w, fit(msg, w), issues_table_available_ ? 7 : 4, true);
        }

        if (line < y + h) {
            put_line(line++, x, w, "ID   PRI     STATUS       LABEL        ASSIGNEE   TITLE", 7, true);
        }

        for (const auto& issue : issues_) {
            if (line >= y + h) break;
            std::ostringstream oss;
            oss << "#" << std::setw(3) << issue.id << " "
                << std::left << std::setw(8) << issue.priority
                << std::setw(12) << issue.status
                << std::setw(12) << issue.label
                << std::setw(10) << issue.assignee
                << fit(issue.title, 28);

            int color = color_for_priority(issue.priority);
            if (issue.status == "review") color = 2;
            if (issue.status == "open") color = 1;
            put_line(line++, x, w, fit(oss.str(), w), color);
        }

        if (line < y + h) put_line(line++, x, w, "", 1);
        if (line < y + h) {
            std::ostringstream ss;
            ss << sprint_.name << "  " << sprint_.start_date << " -> " << sprint_.end_date
               << "  bonus +" << sprint_.bonus_cp << "CP for participants";
            put_line(line++, x, w, fit(ss.str(), w), 4);
        }
        if (line < y + h) {
            std::ostringstream ids;
            ids << "Sprint issues: ";
            for (size_t i = 0; i < sprint_.issue_ids.size(); ++i) {
                if (i) ids << ", ";
                ids << "#" << sprint_.issue_ids[i];
            }
            put_line(line++, x, w, fit(ids.str(), w), 7);
        }

        if (line < y + h) put_line(line++, x, w, "", 1);
        if (line < y + h) put_line(line++, x, w, "CP for dev contribution (from spec):", 7, true);
        if (line < y + h) put_line(line++, x, w, "Issue create +3 | close +10~30 | review +5 | PR merge +15/30/50", 1);
        if (line < y + h) put_line(line++, x, w, "Docs +10 | design review +5", 1);
    }

    void handle_key(int ch, bool& running) {
        switch (ch) {
            case 'q':
            case 'Q':
                running = false;
                break;
            case '1': page_ = 1; break;
            case '2': page_ = 2; break;
            case '3': page_ = 3; break;
            case '4': page_ = 4; break;
            case '5': page_ = 5; break;
            case 'j':
            case KEY_DOWN:
                if (page_ == 2) {
                    selected_member_row_ = clampi(selected_member_row_ + 1, 0, static_cast<int>(members_.size()) - 1);
                }
                break;
            case 'k':
            case KEY_UP:
                if (page_ == 2) {
                    selected_member_row_ = clampi(selected_member_row_ - 1, 0, static_cast<int>(members_.size()) - 1);
                }
                break;
            case 's':
            case 'S':
                if (page_ == 2) {
                    sort_key_ = static_cast<SortKey>((static_cast<int>(sort_key_) + 1) % 8);
                }
                break;
            case 'a':
            case 'A':
                if (page_ == 3) {
                    channel_activity_range_ = ChannelActivityRange::All;
                }
                break;
            case 'm':
            case 'M':
                if (page_ == 3) {
                    channel_activity_range_ = ChannelActivityRange::Month;
                }
                break;
            case 'w':
            case 'W':
                if (page_ == 3) {
                    channel_activity_range_ = ChannelActivityRange::Week;
                }
                break;
            case 'r':
            case 'R':
                refresh_from_db(true);
                break;
            case KEY_MOUSE:
                handle_mouse();
                break;
            default:
                break;
        }
    }
};

}  // namespace

int main() {
    DashboardApp app;
    app.run();
    return 0;
}
