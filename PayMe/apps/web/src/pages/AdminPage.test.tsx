import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { AppProvider } from "../context/AppContext";
import { AdminPage } from "./AdminPage";

const fetchMock = vi.fn();
(globalThis as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
});

test("admin page loads overview and user stats", async () => {
  fetchMock
    .mockResolvedValueOnce({ ok: true, json: async () => ({ users: 2, settlements: 20 }) })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: "u1", username: "tester", email: "t@example.com", state: "NY", match_count: 4 }],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: "s1", title: "Settlement", status: "open", feature_index_count: 2 }],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [{ id: "e1", type: "match_run_completed", user_id: "u1" }],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        user_id: "u1",
        total_match_results: 10,
        latest_run_id: "r1",
        latest_run_result_count: 3,
        average_score: 0.8,
        gmail_messages: 1000,
        plaid_transactions: 1000,
      }),
    });

  render(
    <AppProvider>
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    </AppProvider>,
  );

  await waitFor(() => expect(screen.getByText("Admin Observatory")).toBeTruthy());
  await waitFor(() => expect(screen.getByText("t@example.com")).toBeTruthy());
  fireEvent.change(screen.getByDisplayValue("Select user for stats"), { target: { value: "u1" } });
  fireEvent.click(screen.getByText("Load user stats"));
  await waitFor(() => expect(screen.getAllByText("1000").length).toBeGreaterThan(0));
});
