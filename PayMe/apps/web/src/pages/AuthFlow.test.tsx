import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { LoginPage } from "./LoginPage";
import { OnboardingPage } from "./OnboardingPage";
import { SignupPage } from "./SignupPage";

const fetchMock = vi.fn();
global.fetch = fetchMock;

beforeEach(() => {
  fetchMock.mockReset();
});

test("signup form submits and navigates", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    json: async () => ({ access_token: "t" })
  });
  render(
    <MemoryRouter initialEntries={["/signup"]}>
      <Routes>
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/onboarding" element={<div>Onboarding Target</div>} />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByPlaceholderText("Username"), { target: { value: "matt" } });
  fireEvent.change(screen.getByPlaceholderText("Email"), { target: { value: "matt@example.com" } });
  fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "password123" } });
  fireEvent.click(screen.getByText("Create account"));
  await waitFor(() => expect(screen.getByText("Onboarding Target")).toBeTruthy());
});

test("login form renders and calls API", async () => {
  fetchMock.mockResolvedValue({
    ok: true,
    json: async () => ({ access_token: "t" })
  });
  render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/matches" element={<div>Matches Target</div>} />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByPlaceholderText("Username or email"), { target: { value: "matt" } });
  fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "password123" } });
  fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
});

test("onboarding submits then skip runs first match", async () => {
  fetchMock
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({})
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({})
    });
  render(
    <MemoryRouter initialEntries={["/onboarding"]}>
      <Routes>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/matches" element={<div>Matches Target</div>} />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.change(screen.getByPlaceholderText("First name"), { target: { value: "Matt" } });
  fireEvent.change(screen.getByPlaceholderText("Last name"), { target: { value: "H" } });
  fireEvent.click(screen.getByText("Finish onboarding"));
  await waitFor(() => expect(screen.getByText("Skip for now")).toBeTruthy());
  fireEvent.click(screen.getByText("Skip for now"));
  fireEvent.click(screen.getByText("Run first match"));
  await waitFor(() => expect(screen.getByText("Matches Target")).toBeTruthy());
});
