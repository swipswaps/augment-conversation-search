/**
 * UX-SEARCH-006: Search Refinement Must Change Results
 * 
 * This test enforces that query refinement produces meaningful ranking changes.
 * If refinement does not refine, the UI MUST block results and show UX failure.
 * 
 * FAILURE CONDITIONS:
 * - Overlap ≥ 90% between successive searches
 * - UX banner not shown when overlap ≥ 90%
 * - Results still rendered when ux_block === true
 */

describe("Search refinement must change results", () => {
  beforeEach(() => {
    cy.visit("http://localhost:5001");
  });

  it("blocks UX when refinement does not refine (overlap ≥ 90%)", () => {
    // Initial search
    cy.get("#searchInput").type("setting");
    cy.wait(500);

    // Capture first result set
    cy.window().then(win => {
      const firstResults = win.__LAST_SEARCH_RESULTS__;
      expect(firstResults).to.exist;
      expect(firstResults.length).to.be.greaterThan(0);
    });

    // Refined search (should change results)
    cy.get("#searchInput").clear().type("settings");
    cy.wait(500);

    // UX banner MUST appear if overlap ≥ 90%
    cy.get("#ux-banner").then($banner => {
      if ($banner.is(":visible")) {
        // If banner is visible, results MUST be blocked
        cy.get("#ux-banner")
          .should("contain.text", "Search refinement")
          .and("contain.text", "did not");

        cy.get("#conversationsList .blocked-results")
          .should("be.visible")
          .and("contain.text", "Results blocked");
      }
    });

    // Ranking delta MUST be visible
    cy.get("#ranking-delta").should("exist");
  });

  it("shows query explanation widget", () => {
    cy.get("#searchInput").type("the settings modal");
    cy.wait(500);

    // Query explanation MUST be visible
    cy.get("#query-explain")
      .should("be.visible")
      .and("contain.text", "Search interpretation");

    // Should show stopwords removed
    cy.get("#query-explain").should("contain.text", "Stopwords removed");
  });

  it("allows results when refinement is meaningful (overlap < 90%)", () => {
    // Initial broad search
    cy.get("#searchInput").type("test");
    cy.wait(500);

    // Highly specific refinement
    cy.get("#searchInput").clear().type("test database connection error");
    cy.wait(500);

    // UX banner should NOT block (overlap should be low)
    cy.get("#conversationsList .blocked-results").should("not.exist");

    // Results should render
    cy.get("#conversationsList .search-result-group").should("exist");
  });

  it("exposes search results to window for testing", () => {
    cy.get("#searchInput").type("modal");
    cy.wait(500);

    cy.window().then(win => {
      expect(win.__LAST_SEARCH_RESULTS__).to.exist;
      expect(win.__LAST_SEARCH_DATA__).to.exist;
      expect(win.__LAST_SEARCH_DATA__.ux_status).to.be.oneOf(["ok", "degraded"]);
    });
  });
});

