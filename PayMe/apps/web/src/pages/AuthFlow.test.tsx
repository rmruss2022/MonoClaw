import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { AppProvider } from "../context/AppContext";
import { LoginPage } from "./LoginPage";
import { OnboardingPage } from "./OnboardingPage";
import { SignupPage } from "./SignupPage";

const fetchMock = vi.fn();
(globalThis as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;

beforeEach(() => {
  localStorage.clear();
  fetchMock.mockReset();
});

test("signup form submits and advances to step 2", async () => {
  fetchMock
    .mockResolvedValueOnce({ ok: true, json: async () => ({ access_token: "t" }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ id: "u1", username: "matt", email: "matt@example.com", gmail_oauth_connected: false, plaid_linked: false }) });
  render(
    <MemoryRouter initialEntries={["/signup"]}>
      <AppProvider>
        <Routes>
          <Route path="/signup" element={<SignupPage />} />
        </Routes>
      </AppProvider>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByPlaceholderText("Username"), { target: { value: "matt" } });
  fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "matt@example.com" } });
  fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "password123" } });
  fireEvent.click(screen.getByText("Create account"));
  await waitFor(() => expect(screen.getByText("About You")).toBeTruthy());
  expect(screen.getByPlaceholderText("First name")).toBeTruthy();
});

test("login form renders and calls API", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    json: async () => ({ access_token: "t" })
  });
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <AppProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<div>Matches Target</div>} />
        </Routes>
      </AppProvider>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByPlaceholderText("Username or email"), { target: { value: "matt" } });
  fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "password123" } });
  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
});

test("onboarding submits profile and navigates to home", async () => {
  fetchMock
    .mockResolvedValueOnce({ ok: true, json: async () => ({}) })   // POST /onboarding
    .mockResolvedValueOnce({ ok: true, json: async () => ({}) });  // POST /match/run
  render(
    <MemoryRouter initialEntries={["/onboarding"]}>
      <AppProvider>
        <Routes>
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/" element={<div>Matches Target</div>} />
        </Routes>
      </AppProvider>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByPlaceholderText("First name"), { target: { value: "Matt" } });
  fireEvent.change(screen.getByPlaceholderText("Last name"), { target: { value: "H" } });
  fireEvent.click(screen.getByText("Finish onboarding"));
  await waitFor(() => expect(screen.getByText("Matches Target")).toBeTruthy());
});
