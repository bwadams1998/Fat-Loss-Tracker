{% extends "base.html" %}
{% block content %}
<section class="card">
  <h2>Targets</h2>
  <form method="post" class="form-grid">
    <label>Start weight<input type="number" step="0.1" name="start_weight" value="{{ goals.start_weight or '' }}"></label>
    <label>Target weight<input type="number" step="0.1" name="target_weight" value="{{ goals.target_weight or '' }}"></label>
    <label>Target date<input type="date" name="target_date" value="{{ goals.target_date or '' }}"></label>
    <label>Calories<input type="number" name="calories" value="{{ goals.calories }}"></label>
    <label>Protein grams<input type="number" name="protein" value="{{ goals.protein }}"></label>
    <label>Steps<input type="number" name="steps" value="{{ goals.steps }}"></label>
    <button>Save targets</button>
  </form>
</section>

<section class="card">
  <h2>Measurements</h2>
  <form method="post" action="{{ url_for('add_measurement') }}" class="form-grid">
    <label>Date<input type="date" name="measure_date" value="{{ today }}"></label>
    <label>Waist<input type="number" step="0.1" name="waist"></label>
    <label>Chest<input type="number" step="0.1" name="chest"></label>
    <label>Arm<input type="number" step="0.1" name="arm"></label>
    <label>Thigh<input type="number" step="0.1" name="thigh"></label>
    <label class="wide">Notes<input name="notes"></label>
    <button>Save measurement</button>
  </form>
  <div class="table-wrap">
    <table>
      <tr><th>Date</th><th>Waist</th><th>Chest</th><th>Arm</th><th>Thigh</th></tr>
      {% for row in measurements %}
      <tr><td>{{ row.measure_date }}</td><td>{{ row.waist or '' }}</td><td>{{ row.chest or '' }}</td><td>{{ row.arm or '' }}</td><td>{{ row.thigh or '' }}</td></tr>
      {% endfor %}
    </table>
  </div>
</section>
{% endblock %}
