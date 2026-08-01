export function FieldInput({ field, value, onChange, options = [] }) {
  const id = `field-${field.name}`;
  const fieldOptions = options.length ? options : field.options || [];

  if (field.type === "checkbox") {
    return (
      <label className="check-field" htmlFor={id}>
        <input
          id={id}
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
          type="checkbox"
        />
        <span>{field.label}</span>
      </label>
    );
  }

  if (field.type === "select") {
    return (
      <label className={`form-field ${field.span === 2 ? "span-2" : ""}`} htmlFor={id}>
        <span>{field.label}</span>
        <select
          id={id}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value)}
          required={field.required}
        >
          <option value="">{field.placeholder || "Select"}</option>
          {fieldOptions.map((option) => {
            const optionValue = typeof option === "object" ? option.value : option;
            const optionLabel = typeof option === "object" ? option.label : option;
            return (
              <option key={optionValue} value={optionValue}>
                {optionLabel}
              </option>
            );
          })}
        </select>
      </label>
    );
  }

  if (field.type === "textarea") {
    return (
      <label className={`form-field ${field.span === 2 ? "span-2" : ""}`} htmlFor={id}>
        <span>{field.label}</span>
        <textarea
          id={id}
          value={value ?? ""}
          onChange={(event) => onChange(event.target.value)}
          required={field.required}
          rows={field.rows || 3}
        />
      </label>
    );
  }

  return (
    <label className={`form-field ${field.span === 2 ? "span-2" : ""}`} htmlFor={id}>
      <span>{field.label}</span>
      <input
        id={id}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        required={field.required}
        type={field.type || "text"}
        step={field.step}
      />
    </label>
  );
}

export function LineCellInput({ field, value, onChange, options = [] }) {
  const commonProps = {
    className: "line-cell-control",
    value: value ?? "",
    onChange: (event) => onChange(event.target.value),
    required: field.required,
  };

  if (field.type === "select") {
    return (
      <select {...commonProps}>
        <option value="">{field.placeholder || "Select"}</option>
        {options.map((option) => {
          const optionValue = typeof option === "object" ? option.value : option;
          const optionLabel = typeof option === "object" ? option.label : option;
          return (
            <option key={optionValue} value={optionValue}>
              {optionLabel}
            </option>
          );
        })}
      </select>
    );
  }

  return <input {...commonProps} step={field.step} type={field.type || "text"} />;
}
