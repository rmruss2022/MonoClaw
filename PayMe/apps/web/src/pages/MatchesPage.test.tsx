import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { AppProvider } from "../context/AppContext";
import { MatchesPage } from "./MatchesPage";

const fetchMock = vi.fn();
(globalThis as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
});

test("matches render and pin triggers API", async () => {
  fetchMock
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          settlement_id: "1",
          title: "Pinned Settlement",
          score: 0.99,
          pinned: true,
          reasons_json: { matched_features: ["merchant:amazon"], confidence_breakdown: { rules: 0.99 } }
        }
      ]
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ settlement_id: "1", pinned: true })
    })
    .mockResolvedValue({
      ok: true,
      json: async () => [
        {
          settlement_id: "1",
          title: "Pinned Settlement",
          score: 0.99,
          pinned: true,
          reasons_json: { matched_features: ["merchant:amazon"], confidence_breakdown: { rules: 0.99 } }
        }
      ]
    });

  render(
    <MemoryRouter>
      <AppProvider>
        <MatchesPage />
      </AppProvider>
    </MemoryRouter>
  );
  await waitFor(() => expect(screen.getByText(/Pinned Settlement/)).toBeTruthy());
  fireEvent.click(screen.getByText("Unpin"));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(expect.stringMatching(/\/settlements\/1\/pin$/), expect.anything())
  );
});
