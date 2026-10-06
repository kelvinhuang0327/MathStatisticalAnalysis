#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

using Clock = std::chrono::steady_clock;
using Mask = std::uint64_t;

struct ThresholdProfile {
  Mask ge1 = 0;
  Mask ge2 = 0;
  Mask ge3 = 0;
};

using ChooseTable = std::array<std::array<Mask, 8>, 64>;

ChooseTable make_choose_table() {
  ChooseTable choose{};
  for (std::size_t n = 0; n < choose.size(); ++n) {
    choose[n][0] = 1;
    for (std::size_t k = 1; k < choose[n].size(); ++k) {
      if (k <= n) {
        choose[n][k] =
            k == n ? 1 : choose[n - 1][k - 1] + choose[n - 1][k];
      }
    }
  }
  return choose;
}

Mask colex_rank(const std::vector<int>& labels, const ChooseTable& choose) {
  Mask rank = 0;
  for (std::size_t index = 0; index < labels.size(); ++index) {
    rank += choose[static_cast<std::size_t>(labels[index])][index + 1];
  }
  return rank;
}

std::vector<ThresholdProfile> build_profiles(
    int pool_size,
    int subset_size,
    int threshold,
    const std::vector<Mask>& tickets,
    const ChooseTable& choose,
    const Clock::time_point& started,
    double native_limit_seconds,
    bool& timed_out) {
  const auto profile_count =
      choose[static_cast<std::size_t>(pool_size)]
            [static_cast<std::size_t>(subset_size)];
  std::vector<ThresholdProfile> profiles(static_cast<std::size_t>(profile_count));
  std::vector<int> labels(static_cast<std::size_t>(subset_size));
  Mask generated = 0;

  const auto visit = [&](const auto& self, int start, int depth, Mask label_mask) -> void {
    if (timed_out) {
      return;
    }
    if (depth == subset_size) {
      const auto index = colex_rank(labels, choose);
      auto& profile = profiles[static_cast<std::size_t>(index)];
      for (std::size_t ticket = 0; ticket < tickets.size(); ++ticket) {
        const int hits = std::popcount(tickets[ticket] & label_mask);
        if (hits >= 1) {
          profile.ge1 |= Mask{1} << ticket;
        }
        if (hits >= 2) {
          profile.ge2 |= Mask{1} << ticket;
        }
        if (hits >= 3) {
          profile.ge3 |= Mask{1} << ticket;
        }
      }
      ++generated;
      if ((generated & 4095U) == 0U && native_limit_seconds > 0.0) {
        const auto elapsed =
            std::chrono::duration<double>(Clock::now() - started).count();
        timed_out = elapsed >= native_limit_seconds;
      }
      return;
    }

    const int remaining = subset_size - depth;
    for (int label = start; label <= pool_size - remaining; ++label) {
      labels[static_cast<std::size_t>(depth)] = label;
      self(self, label + 1, depth + 1, label_mask | (Mask{1} << label));
      if (timed_out) {
        return;
      }
    }
  };

  visit(visit, 0, 0, 0);
  return profiles;
}

struct Histograms {
  std::vector<Mask> full;
  std::vector<Mask> anchor_exclusive;
  Mask subset_count = 0;
  bool timed_out = false;
};

Histograms count_fast_seven_sets(
    int pool_size,
    int ticket_count,
    int anchor_count,
    Mask outcome_multiplier,
    double native_limit_seconds,
    const std::vector<Mask>& tickets,
    const ChooseTable& choose,
    const Clock::time_point& started) {
  Histograms result{
      std::vector<Mask>(static_cast<std::size_t>(ticket_count + 1), 0),
      std::vector<Mask>(
          static_cast<std::size_t>(ticket_count - anchor_count + 1), 0),
      0,
      false};

  auto triples = build_profiles(
      pool_size, 3, 3, tickets, choose, started, native_limit_seconds,
      result.timed_out);
  auto quads = build_profiles(
      pool_size, 4, 3, tickets, choose, started, native_limit_seconds,
      result.timed_out);
  if (result.timed_out) {
    return result;
  }

  const Mask anchor_mask =
      anchor_count == 0 ? 0 : (Mask{1} << anchor_count) - 1;
  for (int a = 0; a <= pool_size - 7; ++a) {
    for (int b = a + 1; b <= pool_size - 6; ++b) {
      for (int c = b + 1; c <= pool_size - 5; ++c) {
        const auto triple_index =
            choose[static_cast<std::size_t>(a)][1] +
            choose[static_cast<std::size_t>(b)][2] +
            choose[static_cast<std::size_t>(c)][3];
        const auto& first = triples[static_cast<std::size_t>(triple_index)];
        for (int d = c + 1; d <= pool_size - 4; ++d) {
          for (int e = d + 1; e <= pool_size - 3; ++e) {
            for (int f = e + 1; f <= pool_size - 2; ++f) {
              for (int g = f + 1; g < pool_size; ++g) {
                const auto quad_index =
                    choose[static_cast<std::size_t>(d)][1] +
                    choose[static_cast<std::size_t>(e)][2] +
                    choose[static_cast<std::size_t>(f)][3] +
                    choose[static_cast<std::size_t>(g)][4];
                const auto& second = quads[static_cast<std::size_t>(quad_index)];
                const Mask winners =
                    first.ge3 | (first.ge2 & second.ge1) |
                    (first.ge1 & second.ge2) | second.ge3;
                const int total_winners = std::popcount(winners);
                result.full[static_cast<std::size_t>(total_winners)] +=
                    outcome_multiplier;
                if ((winners & anchor_mask) == 0) {
                  const int residual_winners =
                      std::popcount(winners >> anchor_count);
                  result.anchor_exclusive[
                      static_cast<std::size_t>(residual_winners)] +=
                      outcome_multiplier;
                }
                ++result.subset_count;
                if ((result.subset_count & ((Mask{1} << 20) - 1)) == 0 &&
                    native_limit_seconds > 0.0) {
                  const auto elapsed =
                      std::chrono::duration<double>(Clock::now() - started)
                          .count();
                  if (elapsed >= native_limit_seconds) {
                    result.timed_out = true;
                    return result;
                  }
                }
              }
            }
          }
        }
      }
    }
  }
  return result;
}

Histograms count_generic_sets(
    int pool_size,
    int set_size,
    int threshold,
    int ticket_count,
    int anchor_count,
    Mask outcome_multiplier,
    double native_limit_seconds,
    const std::vector<Mask>& tickets,
    const ChooseTable& choose,
    const Clock::time_point& started) {
  Histograms result{
      std::vector<Mask>(static_cast<std::size_t>(ticket_count + 1), 0),
      std::vector<Mask>(
          static_cast<std::size_t>(ticket_count - anchor_count + 1), 0),
      0,
      false};
  const Mask anchor_mask =
      anchor_count == 0 ? 0 : (Mask{1} << anchor_count) - 1;
  std::vector<int> labels(static_cast<std::size_t>(set_size));
  const auto visit = [&](const auto& self, int start, int depth, Mask label_mask) -> void {
    if (result.timed_out) {
      return;
    }
    if (depth == set_size) {
      Mask winners = 0;
      for (std::size_t ticket = 0; ticket < tickets.size(); ++ticket) {
        if (std::popcount(tickets[ticket] & label_mask) >= threshold) {
          winners |= Mask{1} << ticket;
        }
      }
      result.full[static_cast<std::size_t>(std::popcount(winners))] +=
          outcome_multiplier;
      if ((winners & anchor_mask) == 0) {
        result.anchor_exclusive[static_cast<std::size_t>(
            std::popcount(winners >> anchor_count))] += outcome_multiplier;
      }
      ++result.subset_count;
      if ((result.subset_count & 65535U) == 0U && native_limit_seconds > 0.0) {
        const auto elapsed =
            std::chrono::duration<double>(Clock::now() - started).count();
        result.timed_out = elapsed >= native_limit_seconds;
      }
      return;
    }

    const int remaining = set_size - depth;
    for (int label = start; label <= pool_size - remaining; ++label) {
      labels[static_cast<std::size_t>(depth)] = label;
      self(self, label + 1, depth + 1, label_mask | (Mask{1} << label));
      if (result.timed_out) {
        return;
      }
    }
  };
  visit(visit, 0, 0, 0);
  return result;
}

void print_histogram(const std::vector<Mask>& histogram) {
  std::cout << '[';
  for (std::size_t index = 0; index < histogram.size(); ++index) {
    if (index != 0) {
      std::cout << ',';
    }
    std::cout << histogram[index];
  }
  std::cout << ']';
}

}  // namespace

int main() {
  std::ios::sync_with_stdio(false);
  std::cin.tie(nullptr);

  int pool_size = 0;
  int set_size = 0;
  int threshold = 0;
  int ticket_count = 0;
  int anchor_count = 0;
  Mask outcome_multiplier = 0;
  double native_limit_seconds = 0.0;
  if (!(std::cin >> pool_size >> set_size >> threshold >> ticket_count >>
        anchor_count >> outcome_multiplier >> native_limit_seconds)) {
    std::cerr << "missing histogram configuration\n";
    return 64;
  }
  if (pool_size < 1 || pool_size > 63 || set_size < 1 ||
      set_size > pool_size || threshold < 1 || threshold > set_size ||
      ticket_count < 1 || ticket_count > 63 || anchor_count < 0 ||
      anchor_count > ticket_count || outcome_multiplier < 1 ||
      native_limit_seconds < 0.0) {
    std::cerr << "invalid histogram configuration\n";
    return 64;
  }

  std::vector<Mask> tickets(static_cast<std::size_t>(ticket_count));
  for (auto& ticket : tickets) {
    if (!(std::cin >> ticket) || (ticket >> pool_size) != 0) {
      std::cerr << "invalid ticket mask\n";
      return 64;
    }
  }

  const auto started = Clock::now();
  const auto choose = make_choose_table();
  const Histograms result =
      set_size == 7 && threshold == 3
          ? count_fast_seven_sets(
                pool_size, ticket_count, anchor_count, outcome_multiplier,
                native_limit_seconds, tickets, choose, started)
          : count_generic_sets(
                pool_size, set_size, threshold, ticket_count, anchor_count,
                outcome_multiplier, native_limit_seconds, tickets, choose,
                started);
  const double wall_seconds =
      std::chrono::duration<double>(Clock::now() - started).count();
  if (result.timed_out) {
    std::cout << "{\"status\":\"NATIVE_TIMEOUT\",\"subset_count\":"
              << result.subset_count << ",\"native_wall_time_seconds\":"
              << wall_seconds << "}\n";
    return 2;
  }

  std::cout << "{\"status\":\"OK\",\"subset_count\":"
            << result.subset_count << ",\"full_histogram\":";
  print_histogram(result.full);
  std::cout << ",\"anchor_exclusive_histogram\":";
  print_histogram(result.anchor_exclusive);
  std::cout << ",\"native_wall_time_seconds\":" << wall_seconds << "}\n";
  return 0;
}
