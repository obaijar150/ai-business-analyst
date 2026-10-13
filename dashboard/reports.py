from dashboard.insights import generate_insights
from dashboard.models import Report


def create_report(owner, dataset, title=None):
    insights = generate_insights(dataset)
    measure = insights.get("measure") or "value"
    kpis = insights.get("kpis", [])
    top_products = insights.get("top_products", [])
    worst_products = insights.get("worst_products", [])
    anomalies = insights.get("anomalies", [])
    recommendations = insights.get("recommendations", [])
    trends = insights.get("trends", {"labels": [], "values": []})
    trend_values = trends.get("values", [])
    trend_direction = "upward" if len(trend_values) >= 2 and trend_values[-1] > trend_values[0] else "flat or downward"

    executive_summary = (
        f"Business report for {dataset.name}. The dataset contains {dataset.row_count} rows. "
        f"The primary measure is {measure}. Top performer: "
        f"{top_products[0]['name'] if top_products else 'not available'}. "
        f"The overall trend is {trend_direction}."
    )
    findings = []
    if top_products:
        findings.append(f"Top performer is {top_products[0]['name']} with {top_products[0]['value']}.")
    if worst_products:
        findings.append(f"Lowest performer is {worst_products[0]['name']} with {worst_products[0]['value']}.")
    if anomalies:
        findings.append(f"{len(anomalies)} anomalies were detected.")
    if not findings:
        findings.append("No notable findings were detected.")

    title = title or f"Business Report - {dataset.name}"
    report = Report.objects.create(
        owner=owner,
        dataset=dataset,
        title=title,
        executive_summary=executive_summary,
        kpis=kpis,
        trends=trends.get("labels", []) and [{"labels": trends.get("labels", []), "values": trends.get("values", [])}],
        anomalies=anomalies,
        findings=findings,
        recommendations=recommendations,
        evidence={
            "dataset": dataset.name,
            "rows_examined": dataset.row_count,
            "period": "All dataset rows; no period filter was applied.",
            "calculation": "All metrics were calculated with Pandas from the stored dataset.",
        },
        charts=insights.get("charts", []),
    )
    return report