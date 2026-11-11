// The person who starts a match gets an owner token, shown once. It is what lets them move money in
// the Shield, so it lives only in this browser. Anyone else with the link can watch but not act.
const KEY = "haggle:owner:";

export function saveOwnerToken(dealId: string, token: string): void {
  try {
    localStorage.setItem(KEY + dealId, token);
  } catch {
    // Storage can be blocked. The match still plays, but the Shield then stays view-only.
  }
}

export function ownerToken(dealId: string): string | null {
  try {
    return localStorage.getItem(KEY + dealId);
  } catch {
    return null;
  }
}
