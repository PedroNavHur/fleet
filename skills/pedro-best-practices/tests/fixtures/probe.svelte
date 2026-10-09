<script lang="ts">
  export let items: number[] = [];

  function label(count: number, loading: boolean): string {
    if (loading && count === 0) {
      return "Loading";
    } else if (count > 10) {
      return count > 100 ? "Many" : "Some";
    }
    return "Few";
  }
</script>

<p>{label(items.length, false)}</p>
